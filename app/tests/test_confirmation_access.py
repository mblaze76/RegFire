import uuid
from urllib.error import HTTPError
from psycopg import sql
from test_attendee_accounts import AttendeeAccounts
from confirmation_access import email_link
class ReceiptAccess(AttendeeAccounts):
 def test_account_receipt_and_other_account_denied(self):
  flow,_,data=self.setup_order(0);token=self.enrollment(flow)
  o=self.request('/api/events/'+flow+'/checkout/save',data|{'enrollment_token':token},'POST');self.request('/api/checkout/'+o['id']+'/start',{},'POST')
  with self.assertRaises(HTTPError) as e:self.call_public('/api/attendee/receipt',{'order':o['id']})
  self.assertEqual(e.exception.code,401)
  _,cookie=self.call_public('/api/attendee/login',dict(email='synthetic@example.test',password='Synthetic-only-password-987'))
  d,_=self.call_public('/api/attendee/receipt',{'order':o['id']},cookie);self.assertEqual(d['confirmation_id'],o['id']);self.assertIn('data:image/png;base64,',d['html'])
  other=self.request('/api/events/'+flow+'/checkout/save',data|{'request_key':str(uuid.uuid4())},'POST');self.request('/api/checkout/'+other['id']+'/start',{},'POST')
  with self.assertRaises(HTTPError) as e:self.call_public('/api/attendee/receipt',{'order':other['id']},cookie)
  self.assertEqual(e.exception.code,403)
 def test_colleague_link_exact_order_expiry_and_rotation(self):
  flow,_,data=self.setup_order(0);second=data|{'contacts':data['contacts']|{'email':'colleague@example.test'}}
  root=self.request('/api/events/'+flow+'/checkout/group-save',{'request_key':str(uuid.uuid4()),'members':[data,second]},'POST');self.request('/api/checkout/'+root['id']+'/start',{},'POST');ident=root['group_order_ids'][1]
  with self.store.connect() as c:
   o=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(sql.Identifier(self.schema,'registration_orders')),(ident,)).fetchone()[0];link=email_link(c,self.store,o,'https://staging.regfire.events')
  key=link.split('&key=')[1];d,_=self.call_public('/api/attendee/receipt',{'order':ident,'key':key});self.assertEqual(d['confirmation_id'],ident)
  with self.assertRaises(HTTPError):self.call_public('/api/attendee/receipt',{'order':root['id'],'key':key})
  with self.store.connect() as c:email_link(c,self.store,o,'https://staging.regfire.events')
  with self.assertRaises(HTTPError):self.call_public('/api/attendee/receipt',{'order':ident,'key':key})
  with self.store.connect() as c:
   link=email_link(c,self.store,o,'https://staging.regfire.events');c.execute(sql.SQL("UPDATE {} SET expires=now()-interval '1 second'").format(sql.Identifier(self.schema,'confirmation_links')))
  with self.assertRaises(HTTPError):self.call_public('/api/attendee/receipt',{'order':ident,'key':link.split('&key=')[1]})
