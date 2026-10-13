"""Hosted checkout adapters. Only verified server responses establish payment status."""
import base64,hashlib,hmac,json,time
from decimal import Decimal
from urllib.parse import urlencode,quote,urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

class ProviderError(Exception):pass

def request(url,method='GET',data=None,headers=None):
 if __import__('os').environ.get('REGFIRE_STAGING')=='1':raise ProviderError('External payment calls are disabled in synthetic staging.')
 try:
  with urlopen(Request(url,data=data,headers=headers or {},method=method),timeout=20) as r:return json.load(r)
 except (HTTPError,URLError,TimeoutError,ValueError):raise ProviderError('The payment provider did not confirm the request. Check payment status before trying again.') from None

def payment_quote(order):return order.get('payment_quote',order['quote'])
def amount(order):return str(Decimal(payment_quote(order)['grand_total_minor'])/(1 if payment_quote(order)['currency']=='JPY' else 100))

def stripe(c,path,method='GET',data=None,key=None):
 headers={'Authorization':'Bearer '+c['secret'],'Content-Type':'application/x-www-form-urlencoded'}
 if key:headers['Idempotency-Key']=key
 return request('https://api.stripe.com/v1/'+path,method,urlencode(data).encode() if data is not None else None,headers)

def paypal(c,path,method='GET',data=None,key=None):
 base='https://api-m.sandbox.paypal.com' if c['mode']=='sandbox' else 'https://api-m.paypal.com'
 token=request(base+'/v1/oauth2/token','POST',b'grant_type=client_credentials',{'Authorization':'Basic '+base64.b64encode((c['client_id']+':'+c['secret']).encode()).decode(),'Content-Type':'application/x-www-form-urlencoded'})
 headers={'Authorization':'Bearer '+token['access_token'],'Content-Type':'application/json'}
 if key:headers['PayPal-Request-Id']=key
 return request(base+path,method,json.dumps(data).encode() if data is not None else None,headers)

def create(c,order):
 base=c['return_base'];fragment='#event='+order['flow_id']+'&order='+order['id'];success=base+'/payment'+fragment;cancel=base+'/payment'+fragment+'&canceled=1';key=order['id']
 if c['provider']=='stripe':
  d={'mode':'payment','success_url':success,'cancel_url':cancel,'client_reference_id':key,'metadata[regfire_order]':key,'line_items[0][price_data][currency]':payment_quote(order)['currency'].lower(),'line_items[0][price_data][unit_amount]':payment_quote(order)['grand_total_minor'],'line_items[0][price_data][product_data][name]':'Event registration '+key[:8],'line_items[0][quantity]':1}
  r=stripe(c,'checkout/sessions','POST',d,key)
  if bool(r.get('livemode'))!=(c['mode']=='live'):raise ProviderError('Stripe returned a different payment mode.')
  return dict(id=r['id'],url=r['url'])
 d={'intent':'CAPTURE','purchase_units':[{'reference_id':key,'custom_id':key,'amount':{'currency_code':payment_quote(order)['currency'],'value':amount(order)}}],'payment_source':{'paypal':{'experience_context':{'return_url':success,'cancel_url':cancel,'user_action':'PAY_NOW','shipping_preference':'NO_SHIPPING'}}}}
 r=paypal(c,'/v2/checkout/orders','POST',d,key);link=next((x['href'] for x in r.get('links',[]) if x['rel'] in ('payer-action','approve')),None)
 if not link:raise ProviderError('PayPal did not return an approval link.')
 return dict(id=r['id'],url=link)

def verify(c,order,capture=False):
 ident=quote(order['provider_id'],safe='')
 if c['provider']=='stripe':
  r=stripe(c,'checkout/sessions/'+ident)
  if r.get('client_reference_id')!=order['id'] or r.get('currency','').upper()!=payment_quote(order)['currency'] or r.get('amount_total')!=payment_quote(order)['grand_total_minor'] or bool(r.get('livemode'))!=(c['mode']=='live'):raise ProviderError('Payment details do not match this registration.')
  return 'paid' if r.get('payment_status')=='paid' else 'expired' if r.get('status')=='expired' else 'pending'
 r=paypal(c,'/v2/checkout/orders/'+ident)
 units=r.get('purchase_units',[])
 if len(units)!=1 or units[0].get('custom_id')!=order['id'] or units[0].get('amount',{}).get('currency_code')!=payment_quote(order)['currency'] or Decimal(units[0]['amount']['value'])!=Decimal(amount(order)):raise ProviderError('PayPal details do not match this registration.')
 if capture and r.get('status')=='APPROVED':
  paypal(c,'/v2/checkout/orders/'+ident+'/capture','POST',{},order['id']+'-capture')
  return verify(c,order,False)
 captures=units[0].get('payments',{}).get('captures',[])
 if r.get('status')=='COMPLETED' and len(captures)==1:
  cap=captures[0]
  if cap.get('status')=='COMPLETED' and cap.get('amount',{}).get('currency_code')==payment_quote(order)['currency'] and Decimal(cap['amount']['value'])==Decimal(amount(order)):return 'paid'
 return 'expired' if r.get('status')=='VOIDED' else 'pending'

def webhook(c,headers,raw):
 if c['provider']=='stripe':
  parts={};
  for part in headers.get('Stripe-Signature','').split(','):
   key,_,value=part.partition('=');parts.setdefault(key,[]).append(value)
  try:timestamp=int(parts['t'][0])
  except (KeyError,ValueError,IndexError):raise ProviderError('Invalid webhook signature.')
  if abs(time.time()-timestamp)>300:raise ProviderError('Expired webhook signature.')
  digest=hmac.new(c['webhook_secret'].encode(),str(timestamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
  if not any(hmac.compare_digest(digest,s) for s in parts.get('v1',[])):raise ProviderError('Invalid webhook signature.')
  event=json.loads(raw)
  if bool(event.get('livemode'))!=(c['mode']=='live'):raise ProviderError('Webhook mode mismatch.')
  return event
 event=json.loads(raw)
 data={key:headers.get(header,'') for key,header in [('auth_algo','PAYPAL-AUTH-ALGO'),('cert_url','PAYPAL-CERT-URL'),('transmission_id','PAYPAL-TRANSMISSION-ID'),('transmission_sig','PAYPAL-TRANSMISSION-SIG'),('transmission_time','PAYPAL-TRANSMISSION-TIME')]}
 data.update(webhook_id=c['webhook_secret'],webhook_event=event)
 if paypal(c,'/v1/notifications/verify-webhook-signature','POST',data).get('verification_status')!='SUCCESS':raise ProviderError('Invalid PayPal webhook signature.')
 return event
