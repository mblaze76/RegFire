import unittest
from access import AccessError
import attendee_edit
from test_attendee_accounts import AttendeeAccounts
class Edit(AttendeeAccounts):
 def test_ownership_stale_and_no_financial_changes(self):
  flow,_,data=self.setup_order(0);token=self.enrollment(flow);o=self.request('/api/events/'+flow+'/checkout/save',data|{'enrollment_token':token},'POST');self.request('/api/checkout/'+o['id']+'/start',{},'POST')
  from psycopg import sql
  with self.store.connect() as c:account=str(c.execute(sql.SQL('SELECT account_id FROM {} WHERE order_id=%s').format(sql.Identifier(self.schema,'attendee_order_access')),(o['id'],)).fetchone()[0])
  from urllib.error import HTTPError
  with self.assertRaises(HTTPError):self.call_public('/api/attendee/edit?id='+o['id'])
  _,cookie=self.call_public('/api/attendee/login',dict(email='synthetic@example.test',password='Synthetic-only-password-987'))
  me,_=self.call_public('/api/attendee/me',cookie=cookie)
  view,_=self.call_public('/api/attendee/edit?id='+o['id'],cookie=cookie)
  with self.assertRaises(HTTPError):self.call_public('/api/attendee/edit',dict(id=o['id'],version=view['version'],contacts={}),cookie=cookie)
  result=attendee_edit.operation(self.store,account,o['id']);self.assertTrue(result['fields'])
  values={f['id']:result['contacts'][f['id']] for f in result['fields']};key=result['fields'][0]['id'];values[key]='Corrected'
  changed=attendee_edit.operation(self.store,account,o['id'],dict(id=o['id'],version=result['version'],contacts=values));self.assertEqual(changed['contacts'][key],'Corrected')
  with self.assertRaises(ValueError):attendee_edit.operation(self.store,account,o['id'],dict(id=o['id'],version=result['version'],contacts=values))
  with self.assertRaises(ValueError):attendee_edit.operation(self.store,account,o['id'],dict(id=o['id'],version=changed['version'],contacts={'email':'other@example.test'}))
  with self.assertRaises(AccessError):attendee_edit.operation(self.store,'00000000-0000-0000-0000-000000000000',o['id'])
  with self.store.connect() as c:body=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(sql.Identifier(self.schema,'registration_orders')),(o['id'],)).fetchone()[0]
  self.assertEqual(body['status'],'confirmed_free');self.assertEqual(body['quote']['grand_total_minor'],0);self.assertIn('Corrected',[d['value'] for d in body['quote']['details']])
