import unittest,uuid,tempfile,json,time,hmac,hashlib
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import test_events
from test_events import draft
from payment_settings import PaymentSettings
import payment_providers as providers

class PaymentSettingsTests(unittest.TestCase):
 def test_private_storage_masking_mode_and_revision(self):
  with tempfile.TemporaryDirectory() as d:
   p=PaymentSettings(Path(d)/'payments.json');s=p.save(dict(action='connection',revision='initial',connection=dict(name='Sandbox',provider='stripe',mode='sandbox',return_base='http://127.0.0.1:8782',enabled=True,secret_action='replace',secret='sk_test_synthetic',webhook_secret_action='replace',webhook_secret='whsec_synthetic')))
   self.assertNotIn('sk_test_synthetic',json.dumps(s));self.assertEqual(p.path.stat().st_mode&0o777,0o600);self.assertTrue(s['connections'][0]['stored']['secret'])
   with self.assertRaises(ValueError):p.save(dict(action='connection',revision='initial',connection={}))
   with self.assertRaises(ValueError):p.save(dict(action='connection',revision=s['revision'],connection=dict(id=s['connections'][0]['id'],name='Changed',provider='stripe',mode='live')))
 def test_webhook_signature_and_mode(self):
  c=dict(provider='stripe',mode='sandbox',webhook_secret='test-secret');raw=b'{"livemode":false,"id":"evt_test"}';t=int(time.time());sig=hmac.new(b'test-secret',str(t).encode()+b'.'+raw,hashlib.sha256).hexdigest();self.assertEqual(providers.webhook(c,{'Stripe-Signature':f't={t},v1={sig}'},raw)['id'],'evt_test')
  for header in ['',f't={t},v1=wrong',f't={t-600},v1={sig}']:
   with self.assertRaises(providers.ProviderError):providers.webhook(c,{'Stripe-Signature':header},raw)
 def test_provider_paid_requires_matching_amount_and_mode(self):
  c=dict(provider='stripe',mode='sandbox',secret='synthetic');o=dict(id='order',provider_id='cs_synthetic',quote=dict(currency='USD',grand_total_minor=100))
  r=dict(client_reference_id='order',currency='usd',amount_total=100,livemode=False,payment_status='paid')
  with patch.object(providers,'stripe',return_value=r):self.assertEqual(providers.verify(c,o),'paid')
  for changed in [dict(amount_total=1),dict(livemode=True),dict(client_reference_id='other')]:
   with patch.object(providers,'stripe',return_value=r|changed),self.assertRaises(providers.ProviderError):providers.verify(c,o)

class CheckoutStorage(unittest.TestCase):
 setUp=test_events.PostgresTest.setUp;tearDown=test_events.PostgresTest.tearDown;start=test_events.PostgresTest.start;stop=test_events.PostgresTest.stop;request=test_events.PostgresTest.request;auth_headers=test_events.PostgresTest.auth_headers
 def setup_order(self,price=10000):
  self.server.payment_settings_path=Path(self.upload_tmp.name)/'payments.json';event=self.request('/api/events',draft(),'POST');flow=event['id'];page=self.request('/api/events/'+flow+'/registration-page');page['regtypes'][0]['price_minor']=price;page['regtypes'][0]['use_default']=True;page['default_rates']=[]
  self.request('/api/events/'+flow+'/registration-page',page,'PUT');data=dict(regtype_id='attendee',contacts={'first-name':'Test','last-name':'Person','email':'synthetic@example.test'},answers={},sessions=[],extras=[],request_key=str(uuid.uuid4()));return flow,page,data
 def test_quote_server_authoritative_and_free_idempotent(self):
  flow,page,data=self.setup_order(0);base='/api/events/'+flow+'/checkout';q=self.request(base+'/quote',data|dict(total=1),'POST');self.assertEqual(q['grand_total_minor'],0)
  order=self.request(base+'/save',data,'POST');again=self.request(base+'/save',data,'POST');self.assertEqual(order['id'],again['id'])
  done=self.request('/api/checkout/'+order['id']+'/start',{},'POST');self.assertEqual(done['status'],'confirmed_free');self.assertEqual(self.request('/api/checkout/'+order['id']+'/start',{},'POST')['status'],'confirmed_free')
  with self.assertRaises(HTTPError):self.request(base+'/save',data|dict(contacts={}), 'POST')
  with self.assertRaises(HTTPError):self.request(base+'/quote',data|dict(contacts=data['contacts']|{'first-name':'   '}),'POST')
 def test_tax_inventory_promo_and_mismatched_currency(self):
  flow,page,data=self.setup_order();base='/api/events/'+flow;extra=self.request(base+'/extra-options');ident=str(uuid.uuid4());extra['items']=[dict(id=ident,name='Tote',description='',kind='physical',price_minor=2500,inventory=1,variants=[],allow_multiple=True,taxable=True)];self.request(base+'/extra-options',extra,'PUT');data['extras']=[dict(item_id=ident,quantity=1)];q=self.request(base+'/checkout/quote',data,'POST');self.assertTrue(q['tax_pending']);self.assertIsNone(q['grand_total_minor'])
  with self.assertRaises(HTTPError):self.request(base+'/checkout/save',data,'POST')
  cfg=self.request('/api/admin/payments');self.request('/api/admin/payments',dict(action='assignment',revision=cfg['revision'],event_id=flow,connections=[],tax_bps=700),'POST');q=self.request(base+'/checkout/quote',data,'POST');self.assertEqual(q['tax_minor'],175);self.assertEqual(q['grand_total_minor'],12675)
  with self.assertRaises(HTTPError):self.request(base+'/checkout/quote',data|dict(extras=[dict(item_id=ident,quantity=2)]),'POST')
  page['promo_codes']=[dict(code='ONE',type='percent',amount=10,enabled=True,allotment=0)];self.request(base+'/registration-page',page,'PUT')
  with self.assertRaises(HTTPError):self.request(base+'/checkout/quote',data|dict(promo_code='ONE'),'POST')
 def test_checkout_retry_verified_status_and_inventory_hold(self):
  flow,page,data=self.setup_order();cfg=self.request('/api/admin/payments');cfg=self.request('/api/admin/payments',dict(action='connection',revision=cfg['revision'],connection=dict(name='Synthetic test',provider='stripe',mode='sandbox',return_base=self.url,enabled=True,secret_action='replace',secret='sk_test_synthetic',webhook_secret_action='replace',webhook_secret='whsec_synthetic')),'POST');conn=cfg['connections'][0]['id'];self.request('/api/admin/payments',dict(action='assignment',revision=cfg['revision'],event_id=flow,connections=[conn],default=conn,tax_bps=0),'POST');o=self.request('/api/events/'+flow+'/checkout/save',data,'POST')
  with patch.object(providers,'create',return_value=dict(id='cs_synthetic',url='https://checkout.stripe.com/synthetic')) as create:
   a=self.request('/api/checkout/'+o['id']+'/start',dict(connection_id=conn),'POST');b=self.request('/api/checkout/'+o['id']+'/start',dict(connection_id=conn),'POST');self.assertEqual(create.call_count,1);self.assertEqual(a,b);self.assertEqual(a['status'],'payment_pending')
  with patch.object(providers,'verify',return_value='pending'):self.assertEqual(self.request('/api/checkout/'+o['id']+'/status')['status'],'payment_pending')
  with patch.object(providers,'verify',return_value='paid'):self.assertEqual(self.request('/api/checkout/'+o['id']+'/status')['status'],'paid')
 def test_inventory_and_promo_are_held_after_unknown_provider_attempt(self):
  flow,page,data=self.setup_order();page['promo_codes']=[dict(code='LIMIT',type='fixed',amount=1,enabled=True,allotment=1)];self.request('/api/events/'+flow+'/registration-page',page,'PUT');extra=self.request('/api/events/'+flow+'/extra-options');item=str(uuid.uuid4());extra['items']=[dict(id=item,name='Only tote',description='',kind='physical',price_minor=500,inventory=1,variants=[],allow_multiple=False,taxable=False)];self.request('/api/events/'+flow+'/extra-options',extra,'PUT');data.update(promo_code='LIMIT',extras=[dict(item_id=item,quantity=1)])
  cfg=self.request('/api/admin/payments');cfg=self.request('/api/admin/payments',dict(action='connection',revision=cfg['revision'],connection=dict(name='Synthetic',provider='stripe',mode='sandbox',return_base=self.url,enabled=True,secret_action='replace',secret='sk_test_synthetic',webhook_secret_action='replace',webhook_secret='whsec_synthetic')),'POST');cid=cfg['connections'][0]['id'];self.request('/api/admin/payments',dict(action='assignment',revision=cfg['revision'],event_id=flow,connections=[cid],tax_bps=0),'POST');o=self.request('/api/events/'+flow+'/checkout/save',data,'POST')
  with patch.object(providers,'create',side_effect=providers.ProviderError('Timeout')),self.assertRaises(HTTPError):self.request('/api/checkout/'+o['id']+'/start',dict(connection_id=cid),'POST')
  self.assertEqual(self.request('/api/checkout/'+o['id']+'/status')['status'],'starting')
  with self.assertRaises(HTTPError):self.request('/api/events/'+flow+'/checkout/quote',data|dict(request_key=str(uuid.uuid4())),'POST')
  with self.assertRaises(HTTPError):self.request('/api/events/'+flow+'/checkout/quote',data|dict(extras=[],request_key=str(uuid.uuid4())),'POST')
  with patch.object(providers,'create',return_value=dict(id='cs_recovered',url='https://checkout.stripe.com/synthetic')) as create:
   resumed=self.request('/api/checkout/'+o['id']+'/start',dict(connection_id=cid),'POST');self.assertEqual(resumed['id'],o['id']);self.assertEqual(create.call_args.args[1]['id'],o['id'])
 def test_non_owner_settings_and_forged_webhook_denied(self):
  flow,page,data=self.setup_order();cfg=self.request('/api/admin/payments');cfg=self.request('/api/admin/payments',dict(action='connection',revision=cfg['revision'],connection=dict(name='Synthetic',provider='stripe',mode='sandbox',return_base=self.url,enabled=False,webhook_secret_action='replace',webhook_secret='whsec_synthetic')),'POST');cid=cfg['connections'][0]['id']
  with self.assertRaises(HTTPError):self.request('/api/payments/webhook/'+cid,dict(id='forged',livemode=False),'POST')
  from psycopg import sql
  actor=self.access.session(self.raw_session)['id']
  with self.store.connect() as c:c.execute(sql.SQL("UPDATE {} SET role='admin' WHERE id=%s").format(sql.Identifier(self.schema,'access_users')),(actor,))
  with self.assertRaises(HTTPError) as e:self.request('/api/admin/payments')
  self.assertEqual(e.exception.code,403)

class PayPalAdapterTests(unittest.TestCase):
 def test_create_and_capture_use_stable_keys_and_matching_amount(self):
  c=dict(provider='paypal',mode='sandbox',client_id='synthetic',secret='synthetic',return_base='http://127.0.0.1:8783');o=dict(id=str(uuid.uuid4()),flow_id=str(uuid.uuid4()),provider_id='ORDER',quote=dict(currency='USD',grand_total_minor=12345))
  with patch.object(providers,'paypal',return_value={'id':'ORDER','links':[dict(rel='payer-action',href='https://www.sandbox.paypal.com/checkoutnow?token=ORDER')]}) as call:
   self.assertEqual(providers.create(c,o)['id'],'ORDER');args=call.call_args.args;self.assertEqual(args[-1],o['id']);self.assertEqual(args[3]['purchase_units'][0]['amount']['value'],'123.45')
  unit=dict(custom_id=o['id'],amount=dict(currency_code='USD',value='123.45'));approved=dict(status='APPROVED',purchase_units=[unit]);paid=dict(status='COMPLETED',purchase_units=[unit|dict(payments=dict(captures=[dict(status='COMPLETED',amount=dict(currency_code='USD',value='123.45'))]))])
  with patch.object(providers,'paypal',side_effect=[approved,{},paid]) as call:
   self.assertEqual(providers.verify(c,o,True),'paid');self.assertEqual(call.call_args_list[1].args[-1],o['id']+'-capture')
  with patch.object(providers,'paypal',return_value=approved):self.assertEqual(providers.verify(c,o,False),'pending')
  with patch.object(providers,'paypal',return_value=approved|dict(purchase_units=[unit|dict(amount=dict(currency_code='USD',value='1.00'))])),self.assertRaises(providers.ProviderError):providers.verify(c,o)
 def test_webhook_requires_paypal_verification(self):
  c=dict(provider='paypal',webhook_secret='webhook-id');raw=b'{"id":"evt"}'
  with patch.object(providers,'paypal',return_value={'verification_status':'FAILURE'}),self.assertRaises(providers.ProviderError):providers.webhook(c,{},raw)
  with patch.object(providers,'paypal',return_value={'verification_status':'SUCCESS'}):self.assertEqual(providers.webhook(c,{},raw)['id'],'evt')
