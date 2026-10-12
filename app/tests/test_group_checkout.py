import unittest,uuid
from unittest.mock import patch
from urllib.error import HTTPError
from test_checkout import CheckoutStorage
import payment_providers as providers
class GroupCheckoutTests(unittest.TestCase):
 setUp=CheckoutStorage.setUp;tearDown=CheckoutStorage.tearDown;start=CheckoutStorage.start;stop=CheckoutStorage.stop;request=CheckoutStorage.request;auth_headers=CheckoutStorage.auth_headers;setup_order=CheckoutStorage.setup_order
 def group(self,price=0):
  flow,page,data=self.setup_order(price)
  other=data|dict(contacts=data['contacts']|{'first-name':'Colleague','email':'colleague@example.test'})
  payload=dict(request_key=str(uuid.uuid4()),members=[data,other]);return flow,page,payload
 def test_free_group_has_separate_confirmations_and_retry(self):
  flow,page,p=self.group();url='/api/events/'+flow+'/checkout/group-save';o=self.request(url,p,'POST');self.assertEqual(len(set(o['group_order_ids'])),2)
  self.assertEqual(self.request(url,p,'POST')['id'],o['id'])
  done=self.request('/api/checkout/'+o['id']+'/start',{},'POST');self.assertEqual(done['status'],'confirmed_free')
  for ident in o['group_order_ids']:
   doc=self.request('/api/checkout/'+ident+'/confirmation');self.assertEqual(doc['confirmation_id'],ident);self.assertEqual(doc['status'],'confirmed_free')
  with self.assertRaises(HTTPError):self.request('/api/checkout/'+o['group_order_ids'][1]+'/start',{},'POST')
 def test_inventory_is_checked_across_members_atomically(self):
  flow,page,p=self.group();extra=self.request('/api/events/'+flow+'/extra-options');ident=str(uuid.uuid4());extra['items']=[dict(id=ident,name='One tote',description='',kind='physical',price_minor=0,inventory=1,variants=[],allow_multiple=False,taxable=False)];self.request('/api/events/'+flow+'/extra-options',extra,'PUT')
  for m in p['members']:m['extras']=[dict(item_id=ident,quantity=1)]
  with self.assertRaises(HTTPError):self.request('/api/events/'+flow+'/checkout/group-save',p,'POST')
  from psycopg import sql
  with self.store.connect() as c:self.assertEqual(c.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(self.schema,'registration_orders'))).fetchone()[0],0)
 def test_one_payment_aggregate_and_propagation(self):
  flow,page,p=self.group(10000);cfg=self.request('/api/admin/payments');cfg=self.request('/api/admin/payments',dict(action='connection',revision=cfg['revision'],connection=dict(name='Synthetic',provider='stripe',mode='sandbox',return_base=self.url,enabled=True,secret_action='replace',secret='sk_test_synthetic',webhook_secret_action='replace',webhook_secret='whsec_synthetic')),'POST');cid=cfg['connections'][0]['id'];self.request('/api/admin/payments',dict(action='assignment',revision=cfg['revision'],event_id=flow,connections=[cid],tax_bps=0),'POST')
  o=self.request('/api/events/'+flow+'/checkout/group-save',p,'POST');self.assertEqual(o['payment_quote']['grand_total_minor'],20000)
  with patch.object(providers,'create',return_value=dict(id='cs_group',url='https://checkout.stripe.com/synthetic')) as create:
   for _ in range(2):self.request('/api/checkout/'+o['id']+'/start',dict(connection_id=cid),'POST')
   self.assertEqual(create.call_count,1);self.assertEqual(providers.amount(create.call_args.args[1]),'200')
  with patch.object(providers,'verify',return_value='paid'):self.request('/api/checkout/'+o['id']+'/status')
  for ident in o['group_order_ids']:
   doc=self.request('/api/checkout/'+ident+'/confirmation');self.assertEqual(doc['paid_minor'],10000);self.assertTrue(doc['sandbox'])
 def test_colleague_account_token_rejected(self):
  flow,page,p=self.group();p['members'][1]['enrollment_token']='not-yours'
  with self.assertRaises(HTTPError):self.request('/api/events/'+flow+'/checkout/group-save',p,'POST')
 def test_price_change_blocks_group_start(self):
  flow,page,p=self.group();o=self.request('/api/events/'+flow+'/checkout/group-save',p,'POST')
  page['regtypes'][0]['price_minor']=10000;self.request('/api/events/'+flow+'/registration-page',page,'PUT')
  with patch.object(providers,'create') as create,self.assertRaises(HTTPError):self.request('/api/checkout/'+o['id']+'/start',{},'POST')
  create.assert_not_called()
 def test_provider_verifies_aggregate_not_individual_amount(self):
  c=dict(provider='stripe',mode='sandbox',secret='synthetic');o=dict(id='group',provider_id='cs_group',quote=dict(currency='USD',grand_total_minor=10000),payment_quote=dict(currency='USD',grand_total_minor=20000))
  response=dict(client_reference_id='group',currency='usd',amount_total=10000,livemode=False,payment_status='paid')
  with patch.object(providers,'stripe',return_value=response),self.assertRaises(providers.ProviderError):providers.verify(c,o)
  with patch.object(providers,'stripe',return_value=response|dict(amount_total=20000)):self.assertEqual(providers.verify(c,o),'paid')
 def payment_connection(self,flow,tax=0):
  cfg=self.request('/api/admin/payments');cfg=self.request('/api/admin/payments',dict(action='connection',revision=cfg['revision'],connection=dict(name='Synthetic',provider='stripe',mode='sandbox',return_base=self.url,enabled=True,secret_action='replace',secret='sk_test_synthetic',webhook_secret_action='replace',webhook_secret='whsec_synthetic')),'POST');cid=cfg['connections'][0]['id'];self.request('/api/admin/payments',dict(action='assignment',revision=cfg['revision'],event_id=flow,connections=[cid],tax_bps=tax),'POST');return cid
 def test_aggregate_promo_tax_and_allotment(self):
  flow,page,p=self.group(10000);self.payment_connection(flow,700)
  page['promo_codes']=[dict(code='SAVE',type='percent',amount=10,enabled=True,allotment=1)];self.request('/api/events/'+flow+'/registration-page',page,'PUT')
  for m in p['members']:m['promo_code']='SAVE'
  with self.assertRaises(HTTPError):self.request('/api/events/'+flow+'/checkout/group-save',p,'POST')
  page['promo_codes'][0]['allotment']=2;self.request('/api/events/'+flow+'/registration-page',page,'PUT')
  extra=self.request('/api/events/'+flow+'/extra-options');ident=str(uuid.uuid4());extra['items']=[dict(id=ident,name='Tote',description='',kind='physical',price_minor=1000,inventory=2,variants=[],allow_multiple=False,taxable=True)];self.request('/api/events/'+flow+'/extra-options',extra,'PUT')
  for m in p['members']:m['extras']=[dict(item_id=ident,quantity=1)]
  o=self.request('/api/events/'+flow+'/checkout/group-save',p,'POST');q=o['payment_quote'];self.assertEqual((q['subtotal_minor'],q['discount_minor'],q['tax_minor'],q['grand_total_minor']),(22000,2000,140,20140))
 def test_timeout_holds_whole_group_and_expiry_releases(self):
  flow,page,p=self.group(10000);cid=self.payment_connection(flow)
  extra=self.request('/api/events/'+flow+'/extra-options');ident=str(uuid.uuid4());extra['items']=[dict(id=ident,name='Tote',description='',kind='physical',price_minor=0,inventory=2,variants=[],allow_multiple=False,taxable=False)];self.request('/api/events/'+flow+'/extra-options',extra,'PUT')
  for m in p['members']:m['extras']=[dict(item_id=ident,quantity=1)]
  o=self.request('/api/events/'+flow+'/checkout/group-save',p,'POST')
  with patch.object(providers,'create',side_effect=providers.ProviderError('Timeout')),self.assertRaises(HTTPError):self.request('/api/checkout/'+o['id']+'/start',dict(connection_id=cid),'POST')
  with self.assertRaises(HTTPError):self.request('/api/events/'+flow+'/checkout/quote',p['members'][0],'POST')
  with patch.object(providers,'create',return_value=dict(id='cs_retry',url='https://checkout.stripe.com/synthetic')) as create:
   self.request('/api/checkout/'+o['id']+'/start',dict(connection_id=cid),'POST');self.assertEqual(create.call_args.args[1]['id'],o['id'])
  with patch.object(providers,'verify',return_value='expired'):self.request('/api/checkout/'+o['id']+'/status')
  self.request('/api/events/'+flow+'/checkout/group-quote',p|dict(request_key=str(uuid.uuid4())),'POST')
 def test_primary_account_only_and_pending_edit(self):
  from test_attendee_accounts import AttendeeAccounts
  from psycopg import sql
  flow,page,p=self.group();token=self.request('/api/events/'+flow+'/attendee-account',dict(email='synthetic@example.test',password='Synthetic-only-password-987',confirm_password='Synthetic-only-password-987',preview=False),'POST')['enrollment_token'];p['members'][0]['enrollment_token']=token
  first=self.request('/api/events/'+flow+'/checkout/group-save',p,'POST')
  p['request_key']=str(uuid.uuid4());p['members'][1]['contacts']['first-name']='Edited'
  final=self.request('/api/events/'+flow+'/checkout/group-save',p,'POST');self.request('/api/checkout/'+final['id']+'/start',{},'POST')
  with self.store.connect() as c:
   rows=c.execute(sql.SQL('SELECT order_id FROM {}').format(sql.Identifier(self.schema,'attendee_order_access'))).fetchall();self.assertEqual([str(r[0]) for r in rows],[final['id']])
   self.assertEqual(c.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(self.schema,'attendee_accounts'))).fetchone()[0],1)
  with self.assertRaises(HTTPError):self.request('/api/events/'+flow+'/checkout/group-save',p|dict(request_key=str(uuid.uuid4())),'POST')
 def test_session_capacity_and_actor_isolation(self):
  from test_sessions import session
  from psycopg import sql
  flow,page,p=self.group();agenda=self.request('/api/events/'+flow+'/sessions');row=session(capacity=1);agenda['sessions']=[row];agenda=self.request('/api/events/'+flow+'/sessions',agenda,'PUT')
  for m in p['members']:m['sessions']=[row['id']]
  with self.assertRaises(HTTPError):self.request('/api/events/'+flow+'/checkout/group-save',p,'POST')
  agenda['sessions'][0]['capacity']=2;self.request('/api/events/'+flow+'/sessions',agenda,'PUT');o=self.request('/api/events/'+flow+'/checkout/group-save',p,'POST')
  from checkout import get_order
  with self.store.connect() as c:
   for ident in o['group_order_ids']:
    with self.assertRaises(ValueError):get_order(c,self.store,ident,str(uuid.uuid4()))
