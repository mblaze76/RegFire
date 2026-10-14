"""Authenticated local checkout: authoritative quotes, idempotent orders and verified payments."""
import copy,json,re,uuid,time
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit
from psycopg import sql
from psycopg.types.json import Jsonb
import psycopg
from access import AccessError
from payment_settings import PaymentSettings,issues
import payment_providers as providers

ACTIVE=('starting','payment_pending','paid','confirmed_free')
def table(store,name):return sql.Identifier(store.schema,name)
def settings(server):return PaymentSettings(getattr(server,'payment_settings_path',None))
def body(c,store,name,flow,default):
 row=c.execute(sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(table(store,name)),(flow,)).fetchone();return row[0] if row else default

def quote_order(store,c,flow,data,config,exclude=None,extra_held=()):
 from registration import starter,validate_page,pricing_preview,selected_membership
 from demographics import starter as demo_starter,evaluate
 from extra_options import quote as extras_quote
 if not isinstance(data,dict):raise ValueError('Send attendee details.')
 row=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()),(flow,)).fetchone()
 if not row:raise ValueError('Registration flow not found.')
 event=row[0]
 c.execute(sql.SQL('SELECT id FROM {} WHERE id=%s FOR UPDATE').format(store.table()),(event.get('parent_event_id',flow),)).fetchone()
 event=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(store.table()),(flow,)).fetchone()[0]
 if not c.execute(sql.SQL('SELECT 1 FROM {} WHERE id=%s AND NOT archived').format(table(store,'registration_flows')),(flow,)).fetchone():raise ValueError('This flow is unavailable.')
 page=validate_page(body(c,store,'registration_pages',flow,starter(event)),event['timezone']);regtype=data.get('regtype_id');kind=next((r for r in page['regtypes'] if r['id']==regtype),None)
 if not kind:raise ValueError('Choose your registration type.')
 path=data.get('subcategory_path',[]);required,complete=selected_membership(kind,path)
 if not complete:raise ValueError('Choose each registration subcategory.')
 rate=pricing_preview(page,event['timezone'])['regtypes'][regtype]
 if rate.get('price_minor') is None or rate.get('status')=='unavailable':raise ValueError('This registration rate is unavailable.')
 contacts=data.get('contacts',{})
 if not isinstance(contacts,dict) or len(contacts)>50:raise ValueError('Attendee details are invalid.')
 normalized={};details=[]
 for f in page['fields']:
  if f['visible_to'] is not None and regtype not in f['visible_to']:continue
  v=contacts.get(f['id']);typ=f['type'];empty=v is None or v=='' or v is False
  if typ=='address':
   if v is None:v={}
   if not isinstance(v,dict) or any(not isinstance(x,str) or len(x)>500 for x in v.values()):raise ValueError('Check '+f['label']+'.')
   if f['required'] and any(not v.get(k,'').strip() for k in ('line1','city','region','postal','country')):raise ValueError('Complete '+f['label']+'.')
   v={k:v.get(k,'').strip() for k in ('line1','line2','city','region','postal','country')}
  elif typ=='checkbox':
   if v is not None and type(v) is not bool:raise ValueError('Check '+f['label']+'.')
   v=bool(v)
  else:
   if v is None:v=''
   if not isinstance(v,str) or len(v)>10000:raise ValueError('Check '+f['label']+'.')
   v=v.strip()
   if v and typ in ('select','radio') and v not in f['options']:raise ValueError('Choose a current '+f['label']+' option.')
   if v and typ=='email' and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',v):raise ValueError('Enter a valid '+f['label']+'.')
   if v and typ=='number':
    try:
     if not Decimal(v).is_finite():raise ValueError()
    except Exception:raise ValueError('Enter a valid '+f['label']+'.')
  if f['required'] and (v is None or v == '' or v is False):raise ValueError('Complete '+f['label']+'.')
  normalized[f['id']]=v;details.append(dict(id=f['id'],label=f['label'],value=v))
  if typ=='tel' and f.get('sms_consent',f['id']=='cell-phone' or bool(re.search('cell|mobile',f['label'],re.I))):
   consent=data.get('smsConsents',{}).get(f['id'],False)
   if type(consent) is not bool:raise ValueError('Check SMS consent.')
   details.append(dict(label=f['label']+' SMS consent',value=consent))
 demo=body(c,store,'demographics_pages',flow,demo_starter(flow));evaluated=evaluate(demo,page['regtypes'],regtype,data.get('answers',{}),True)
 if evaluated['errors']:raise ValueError('Complete the required demographic answers before continuing.')
 answers=[]
 for q in demo['questions']:
  if q['id'] not in evaluated['visible_ids']:continue
  v=evaluated['effective_answers'].get(q['id']);options={o['id']:o['label'] for o in q.get('options',[])}
  display=[options.get(x,x) for x in v] if isinstance(v,list) else options.get(v,v) if isinstance(v,str) else v
  answers.append(dict(label=q['label'],value=display))
 session_page=body(c,store,'event_sessions',flow,dict(sessions=[],currency=page['currency']));extra_page=body(c,store,'extra_options',flow,dict(items=[],currency=page['currency']))
 chosen=data.get('sessions',[])
 if not isinstance(chosen,list) or len(chosen)>500 or any(not isinstance(x,str) for x in chosen) or len(set(chosen))!=len(chosen):raise ValueError('Session selections are invalid.')
 existing=c.execute(sql.SQL('SELECT id,body FROM {} WHERE flow_id=%s AND status=ANY(%s)').format(table(store,'registration_orders')),(flow,list(ACTIVE))).fetchall();held=[r[1] for r in existing if str(r[0]) not in (exclude if isinstance(exclude,(list,tuple,set)) else [exclude])]+list(extra_held)
 sessions=[];lines=[dict(name=kind['name'],quantity=1,unit_price_minor=rate['price_minor'],line_total_minor=rate['price_minor'],kind='registration')]
 for ident in chosen:
  item=next((s for s in session_page['sessions'] if s['id']==ident),None)
  if not item or item['status']!='active':raise ValueError('A selected session is no longer available.')
  used=sum(ident in o['data'].get('sessions',[]) for o in held)
  if item.get('capacity') is not None and used>=item['capacity']:raise ValueError(item['title']+' is full.')
  sessions.append(dict(id=ident,title=item['title'],start=item['start'],end=item['end'],location=item.get('location','')));lines.append(dict(name=item['title'],quantity=1,unit_price_minor=item['price_minor'],line_total_minor=item['price_minor'],kind='session'))
 if chosen and session_page['currency']!=page['currency']:raise ValueError('The organizer must align session and registration currencies.')
 extra=extras_quote(extra_page,data.get('extras',[]))
 if extra['lines'] and extra['currency']!=page['currency']:raise ValueError('The organizer must align extra-option and registration currencies.')
 for line in extra['lines']:
  item=next(i for i in extra_page['items'] if i['id']==line['item_id']);variant=next((v for v in item['variants'] if v['id']==line['variant_id']),None);stock=(variant or item)['inventory'];used=sum(x['quantity'] for o in held for x in o['data'].get('extras',[]) if x['item_id']==line['item_id'] and x.get('variant_id')==line['variant_id'])
  if stock is not None and line['quantity']+used>stock:raise ValueError(item['name']+' does not have enough remaining inventory.')
  lines.append(line|dict(kind='extra',name=line['name']+(' · '+line['variant'] if line['variant'] else '')))
 promo=data.get('promo_code','')
 if not isinstance(promo,str) or len(promo)>80:raise ValueError('Enter a valid promo code.')
 promo=promo.strip().upper();discount=0
 if promo:
  p=next((p for p in page['promo_codes'] if p['code']==promo and p['enabled']),None)
  if not p:raise ValueError('This promo code is not available.')
  used=sum(o['data'].get('promo_code')==promo for o in held)
  if p['allotment'] is not None and used>=p['allotment']:raise ValueError('This promo code has reached its allotment.')
  base=rate['price_minor'];scale=1 if page['currency']=='JPY' else 100
  discount=base if p['type']=='free' else min(base,int((Decimal(str(p['amount']))*(Decimal(base)/100 if p['type']=='percent' else scale)).quantize(Decimal(1),rounding=ROUND_HALF_UP)))
 assignment=config['assignments'].get(event.get('parent_event_id',flow),{});tax_bps=assignment.get('tax_bps');taxable=sum(x['line_total_minor'] for x in extra['lines'] if x['taxable']);tax_pending=bool(taxable and tax_bps is None);tax=0 if tax_pending else (taxable*(tax_bps or 0)+5000)//10000
 subtotal=sum(l['line_total_minor'] for l in lines);names=[];current=kind
 for ident in path:current=next(x for x in current['subcategories'] if x['id']==ident);names.append(current['name'])
 quote=dict(currency=page['currency'],lines=lines,subtotal_minor=subtotal,discount_minor=discount,tax_minor=None if tax_pending else tax,grand_total_minor=None if tax_pending else subtotal-discount+tax,tax_pending=tax_pending,regtype=kind['name'],subcategories=names,details=details,answers=answers,sessions=sessions,event_name=event['name'])
 clean=dict(regtype_id=regtype,subcategory_path=path,contacts=normalized,answers=evaluated['effective_answers'],sessions=chosen,extras=[dict(item_id=l['item_id'],variant_id=l['variant_id'],quantity=l['quantity']) for l in extra['lines']],promo_code=promo,smsConsents={f['id']:bool(data.get('smsConsents',{}).get(f['id'],False)) for f in page['fields'] if f['id'] in normalized and f['type']=='tel'})
 return quote,clean,event.get('parent_event_id',flow)

def public(order):return {k:v for k,v in order.items() if k not in ('actor_id','connection_snapshot')}
def get_order(c,store,ident,actor=None):
 row=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(table(store,'registration_orders')),(ident,)).fetchone()
 if not row or actor and row[0]['actor_id']!=actor:raise ValueError('Registration not found.')
 return row[0]
def save_order(c,store,o):
 c.execute(sql.SQL('UPDATE {} SET body=%s,status=%s,updated=now() WHERE id=%s').format(table(store,'registration_orders')),(Jsonb(o),o['status'],o['id']))
 from attendee_accounts import complete
 complete(c,store,o)
 from group_checkout import propagate
 if o.get('group_order_ids'):propagate(c,store,o)
 from confirmation_delivery import enqueue
 enqueue(c,store,o)

def handle(h):
 path=urlsplit(h.path).path
 files={'/review':'review.html','/payment':'payment.html','/confirmation':'payment.html','/checkout-site.js':'checkout-site.js','/payment-settings':'payment-settings.html','/payment-settings.js':'payment-settings.js'}
 if h.command=='GET' and path in files:
  content=(Path(__file__).parent/'static'/files[path]).read_bytes();h.send_response(200);h.send_header('Content-Type','text/javascript' if path.endswith('.js') else 'text/html');h.send_header('Content-Length',str(len(content)));h.send_header('Cache-Control','no-store');h.send_header('X-Content-Type-Options','nosniff');h.end_headers();h.wfile.write(content);return True
 admin=path=='/api/admin/payments';m=re.fullmatch(r'/api/events/([a-f0-9-]{36})/checkout/(quote|save|methods|preferences|group-save|group-quote)',path);order_match=re.fullmatch(r'/api/checkout/([a-f0-9-]{36})/(start|status)',path);hook=re.fullmatch(r'/api/payments/webhook/([a-f0-9-]{36})',path)
 if not(admin or m or order_match or hook):return False
 try:
  config=settings(h.server);store=h.server.store;raw=b'';data={}
  if h.command=='POST':
   size=int(h.headers.get('Content-Length',0))
   if not 0<size<=250000:raise ValueError('Request is missing or too large.')
   raw=h.rfile.read(size);data=json.loads(raw)
   if not isinstance(data,dict):raise ValueError('Send an object.')
  if admin:
   from communications import require_owner
   from access_http import access
   require_owner(access(h),h.identity)
   if h.command=='POST':
    if data.get('action')=='test':
     connection=config.connection(data.get('connection_id'));problems=issues(connection)
     if problems:raise ValueError(' '.join(problems))
     if connection['provider']=='stripe':providers.stripe(connection,'balance')
     else:
      import base64
      base='https://api-m.sandbox.paypal.com' if connection['mode']=='sandbox' else 'https://api-m.paypal.com'
      providers.request(base+'/v1/oauth2/token','POST',b'grant_type=client_credentials',{'Authorization':'Basic '+base64.b64encode((connection['client_id']+':'+connection['secret']).encode()).decode(),'Content-Type':'application/x-www-form-urlencoded'})
     h.respond(200,{'message':'Provider authentication succeeded. No charge was made. Checkout and webhook delivery still require an end-to-end sandbox test.'});return True
    if data.get('action')=='connection' and data.get('connection',{}).get('id') and any(data['connection'].get(k+'_action','keep')!='keep' for k in ('secret','client_id')):
     with store.connect() as c:
      if c.execute(sql.SQL("SELECT 1 FROM {} WHERE body->>'connection_id'=%s AND status IN ('starting','payment_pending') LIMIT 1").format(table(store,'registration_orders')),(data['connection']['id'],)).fetchone():raise ValueError('Reconcile pending payments before changing this connection’s API credentials.')
    if data.get('action')=='assignment':access(h).require_event(h.identity,data.get('event_id',''))
    result=config.save(data)
   elif h.command=='GET':result=config.public()
   else:raise ValueError('Use GET or POST.')
   result['events']=[dict(id=e['id'],name=e['name']) for e in access(h).event_list(h.identity)]
   h.respond(200,result);return True
  if hook:
   if h.command!='POST':raise ValueError('Use POST.')
   connection=config.connection(hook[1]);event=providers.webhook(connection,h.headers,raw)
   resource=event.get('data',{}).get('object',{}) if connection['provider']=='stripe' else event.get('resource',{})
   provider_id=resource.get('id') if connection['provider']=='stripe' else resource.get('supplementary_data',{}).get('related_ids',{}).get('order_id')
   with store.connect() as c:
    row=c.execute(sql.SQL("SELECT body FROM {} WHERE body->>'provider_id'=%s AND body->>'connection_id'=%s FOR UPDATE").format(table(store,'registration_orders')),(provider_id,connection['id'])).fetchone()
    if row:
     o=row[0];status=providers.verify(connection,o)
     if status=='paid':o['status']='paid'
     elif status=='expired' and o['status']!='paid':o['status']='expired'
     save_order(c,store,o)
   h.respond(200,{'received':True});return True
  actor=h.identity['id']
  if m:
   flow=str(uuid.UUID(m[1]));action=m[2]
   if action=='preferences':
    if h.command not in ('GET','POST'):raise ValueError('Use GET or POST.')
    from payment_preferences import operation
    h.respond(200,operation(store,flow,data if h.command=='POST' else None));return True
   if action=='methods':
    event=next((e for e in store.list() if e['id']==flow),None)
    if not event:
     with store.connect() as c:event=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()),(flow,)).fetchone()[0]
    cfg=config.read();assignment=cfg['assignments'].get(event.get('parent_event_id',flow),{});available=[dict(id=c['id'],name=c['name'],provider=c['provider'],mode=c['mode'],issues=issues(c)) for c in cfg['connections'] if c['id'] in assignment.get('connections',[])]
    h.respond(200,dict(methods=available,default=assignment.get('default'),preferences=__import__('payment_preferences').operation(store,flow)));return True
   if h.command!='POST':raise ValueError('Use POST.')
   if action in ('group-save','group-quote'):
    from group_checkout import save
    with store.connect() as c:result=save(store,c,flow,actor,data,config.read(),preview=action=='group-quote')
    h.respond(200,result);return True
   # Membership eligibility is checked from saved organizer settings, never a client-supplied page.
   eligibility=store.membership(flow,'check-fields',dict(regtype_id=data.get('regtype_id'),subcategory_path=data.get('subcategory_path',[]),values=data.get('contacts',{})))
   if not eligibility or not eligibility.get('can_continue') or eligibility.get('status')=='pending':raise ValueError('Membership eligibility must be confirmed before checkout.')
   with store.connect() as c:
    row=None
    if action=='save':
     request_key=str(uuid.UUID(data.get('request_key','')))
     row=c.execute(sql.SQL('SELECT body FROM {} WHERE flow_id=%s AND actor_id=%s AND request_key=%s FOR UPDATE').format(table(store,'registration_orders')),(flow,actor,request_key)).fetchone()
    q,clean,parent=quote_order(store,c,flow,data,config.read(),row[0]['id'] if row else None)
    if action=='quote':h.respond(200,q);return True
    if q['tax_pending']:raise ValueError('The organizer must configure tax before this order can be saved for payment.')
    if row:
     o=row[0]
     if o['status']!='pending' and o['data']!=clean:raise ValueError('Payment has started. Finish or reconcile that order before changing it.')
     if o['status']=='pending':o.update(data=clean,quote=q);save_order(c,store,o)
    else:
     o=dict(id=str(uuid.uuid4()),flow_id=flow,parent_event_id=parent,actor_id=actor,data=clean,quote=q,status='pending');c.execute(sql.SQL('INSERT INTO {}(id,flow_id,actor_id,request_key,body,status) VALUES(%s,%s,%s,%s,%s,%s)').format(table(store,'registration_orders')),(o['id'],flow,actor,request_key,Jsonb(o),o['status']))
    from attendee_accounts import bind
    bind(c,store,o,data.get('enrollment_token'))
   h.respond(200,public(o));return True
  if order_match:
   ident=str(uuid.UUID(order_match[1]));action=order_match[2]
   if action=='start' and h.command!='POST':raise ValueError('Use POST.')
   with store.connect() as c:
    o=get_order(c,store,ident,actor)
    from access_http import access
    if h.identity.get('role')=='public-attendee':
     if h.identity.get('public_flow')!=o['flow_id']:raise ValueError('Registration not found.')
    else:access(h).require_event(h.identity,o['flow_id'])
    if o.get('group_parent_id',o['id'])!=o['id']:raise ValueError('Use the combined checkout for this attendee.')
    if action=='status':
     if o.get('provider_id') and o['status'] not in ('paid','confirmed_free','expired'):
      connection=config.connection(o['connection_id']);status=providers.verify(connection,o,capture=h.command=='POST')
      if status=='paid':o['status']='paid'
      elif status=='expired':o['status']='expired'
      save_order(c,store,o)
     c.commit();h.respond(200,public(o));return True
    if o['status'] in ('paid','confirmed_free'):h.respond(200,public(o));return True
    if o['status']=='expired':raise ValueError('This checkout expired. Start a new registration attempt.')
    if o['status']=='pending':
     if o.get('group_order_ids'):
      from group_checkout import revalidate
      q,parent=revalidate(store,c,o,config.read())
     else:
      eligibility=store.membership(o['flow_id'],'check-fields',dict(regtype_id=o['data']['regtype_id'],subcategory_path=o['data']['subcategory_path'],values=o['data']['contacts']))
      if not eligibility or not eligibility.get('can_continue') or eligibility.get('status')=='pending':raise ValueError('Membership eligibility must be confirmed before payment.')
      q,clean,parent=quote_order(store,c,o['flow_id'],o['data'],config.read(),o['id'])
      if q!=o['quote']:raise ValueError('Prices or selections changed. Return to Verify your details before paying.')
     if q['grand_total_minor']==0:o['status']='confirmed_free';save_order(c,store,o);c.commit();h.respond(200,public(o));return True
     connection=config.connection(data.get('connection_id'))
     if connection['id'] not in config.read()['assignments'].get(parent,{}).get('connections',[]):raise ValueError('This payment connection is not assigned to the event.')
     problems=issues(connection)
     if problems:raise ValueError(' '.join(problems))
     o.update(status='starting',started_at=time.time(),connection_id=connection['id'],mode=connection['mode'],provider=connection['provider']);save_order(c,store,o)
   # Commit the inventory hold before any network call. Retries reuse the same idempotency key.
   with store.connect() as c:
    o=get_order(c,store,ident,actor)
    if o['status']=='starting':
     if time.time()-o.get('started_at',0)>18000:raise ValueError('This payment attempt needs provider reconciliation before another creation request. Contact the organizer.')
     connection=config.connection(o['connection_id']);result=providers.create(connection,o);host=urlsplit(result['url']).hostname or ''
     if urlsplit(result['url']).scheme!='https' or not(host=='checkout.stripe.com' if connection['provider']=='stripe' else host in ('www.paypal.com','www.sandbox.paypal.com')):raise providers.ProviderError('Provider returned an unexpected checkout destination.')
     o.update(provider_id=result['id'],checkout_url=result['url'],status='payment_pending');save_order(c,store,o)
   h.respond(200,public(o));return True
 except AccessError as e:h.respond(e.status,{'error':str(e)})
 except providers.ProviderError as e:h.respond(400 if hook else 503,{'error':str(e)})
 except (ValueError,TypeError,KeyError,AttributeError) as e:h.respond(400,{'error':str(e) if isinstance(e,ValueError) else 'Invalid checkout request.'})
 except (psycopg.Error,OSError):h.respond(503,{'error':'Checkout storage is unavailable. Your payment is not confirmed; retry status before paying again.'})
 return True
