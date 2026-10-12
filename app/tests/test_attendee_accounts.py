import json,uuid,unittest
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
from psycopg import sql
from test_checkout import CheckoutStorage
from attendee_accounts import prepare,throttle,_attempts

class AttendeeAccounts(CheckoutStorage):
 def call_public(self,path,data=None,cookie='',csrf=''):
  headers={'Origin':self.url,'Content-Type':'application/json','Cookie':cookie,'X-Attendee-CSRF':csrf}
  r=build_opener(ProxyHandler({})).open(Request(self.url+path,data=None if data is None else json.dumps(data).encode(),headers=headers))
  return json.load(r),r.headers.get('Set-Cookie','').split(';')[0]
 def enrollment(self,flow,address='synthetic@example.test',password='Synthetic-only-password-987'):
  return self.request('/api/events/'+flow+'/attendee-account',dict(email=address,password=password,confirm_password=password,preview=False),'POST')['enrollment_token']
 def test_completion_login_and_isolation(self):
  _attempts.clear();flow,page,data=self.setup_order(0);token=self.enrollment(flow)
  with self.assertRaises(HTTPError):self.call_public('/api/attendee/login',dict(email='synthetic@example.test',password='Synthetic-only-password-987'))
  order=self.request('/api/events/'+flow+'/checkout/save',data|{'enrollment_token':token},'POST')
  self.assertNotIn('password',json.dumps(order));self.assertNotIn(token,json.dumps(order))
  self.request('/api/checkout/'+order['id']+'/start',{},'POST')
  _,cookie=self.call_public('/api/attendee/login',dict(email='synthetic@example.test',password='Synthetic-only-password-987'))
  me,_=self.call_public('/api/attendee/me',cookie=cookie);self.assertEqual(me['user']['email'],'synthetic@example.test')
  rows,_=self.call_public('/api/attendee/registrations',cookie=cookie);self.assertEqual([o['id'] for o in rows['registrations']],[order['id']])
  rows,_=self.call_public('/api/attendee/registrations?event='+str(uuid.uuid4()),cookie=cookie);self.assertEqual(rows['registrations'],[])
  with self.assertRaises(HTTPError):self.call_public('/api/attendee/registrations')
  with self.assertRaises(HTTPError):self.call_public('/api/events/'+flow,cookie=cookie)
  with self.assertRaises(HTTPError):self.call_public('/api/attendee/logout',{},cookie=cookie)
  self.call_public('/api/attendee/logout',{},cookie,me['user']['csrf'])
  with self.assertRaises(HTTPError):self.call_public('/api/attendee/registrations',cookie=cookie)
  with self.store.connect() as c:
   encoded=c.execute(sql.SQL('SELECT password_hash FROM {}').format(sql.Identifier(self.schema,'attendee_accounts'))).fetchone()[0];self.assertNotIn('Synthetic-only',encoded)
 def test_preview_mismatch_existing_account_and_flow_binding(self):
  _attempts.clear();flow,page,data=self.setup_order(0)
  for patch in ({'preview':True},{'confirm_password':'wrong'}):
   with self.assertRaises(HTTPError):self.request('/api/events/'+flow+'/attendee-account',dict(email='synthetic@example.test',password='Synthetic-only-password-987',confirm_password='Synthetic-only-password-987',preview=False)|patch,'POST')
  token=self.enrollment(flow);other,_,otherdata=self.setup_order(0)
  with self.assertRaises(HTTPError):self.request('/api/events/'+other+'/checkout/save',otherdata|{'enrollment_token':token},'POST')
  order=self.request('/api/events/'+flow+'/checkout/save',data|{'enrollment_token':token},'POST');self.request('/api/checkout/'+order['id']+'/start',{},'POST')
  with self.assertRaises(HTTPError):self.enrollment(other,password='A-different-password-123')
  self.assertTrue(self.enrollment(other))
 def test_login_rate_limit(self):
  _attempts.clear()
  for i in range(12):throttle(('synthetic',1))
  from access import AccessError
  with self.assertRaises(AccessError):throttle(('synthetic',1))
