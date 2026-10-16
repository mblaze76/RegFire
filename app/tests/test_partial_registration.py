import unittest,uuid,hashlib
from datetime import datetime,timezone
from unittest.mock import patch,Mock
from psycopg import sql
from psycopg.types.json import Jsonb
import test_checkout as tc
import partial_registration as pr,publication,publication_snapshot as ps
from communications_providers import DeliveryError
class Retention(unittest.TestCase):
 def test_thirty_days_after_event_in_its_timezone(self):
  self.assertEqual(pr.cutoff(dict(end='2027-03-01T17:00',timezone='America/New_York')).isoformat(),'2027-03-31T21:00:00+00:00')
  for event in [{},dict(end='',timezone='UTC'),dict(end='2027-03-14T02:30',timezone='America/New_York')]:
   with self.assertRaises(ValueError):pr.cutoff(event)
class Partials(unittest.TestCase):
 setUp=tc.CheckoutStorage.setUp;tearDown=tc.CheckoutStorage.tearDown;start=tc.CheckoutStorage.start;stop=tc.CheckoutStorage.stop;request=tc.CheckoutStorage.request;auth_headers=tc.CheckoutStorage.auth_headers;setup_order=tc.CheckoutStorage.setup_order
 def fixture(self):
  flow,page,data=self.setup_order(0)
  with self.store.connect() as c:
   event=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(self.store.table()),(flow,)).fetchone()[0];event.update(start='2027-03-01T09:00',end='2027-03-01T17:00')
   c.execute(sql.SQL('UPDATE {} SET body=%s WHERE id=%s').format(self.store.table()),(Jsonb(event),flow))
   account=str(uuid.uuid4());c.execute(sql.SQL('INSERT INTO {}(id,email,password_hash) VALUES(%s,%s,%s)').format(pr.table(self.store,'attendee_accounts')),(account,'synthetic@example.test',__import__('attendee_accounts').password_hash('Test123')))
  review=publication.state(self.store,flow);publication.state(self.store,flow,dict(published=True,revision=0,review_digest=review['review_digest']))
  return flow,account,data
 def test_save_excludes_secrets_and_scoped_list(self):
  flow,account,data=self.fixture();saved=pr.save(self.store,flow,account,data|dict(password='never-store',enrollment_token='never-store',card_number='never-store',contacts=data['contacts']|{'unknown':'never-store'}));pr.save(self.store,flow,account,data)
  rows=pr.listing(self.store,flow);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['id'],saved['id']);self.assertNotIn('never-store',str(pr.review(self.store,flow,saved['id'])));
  with self.store.connect() as c:self.assertNotIn('never-store',str(c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(pr.table(self.store)),(saved['id'],)).fetchone()))
  self.assertEqual(pr.listing(self.store,str(uuid.uuid4())),[])
  with self.assertRaises(ValueError):pr.review(self.store,str(uuid.uuid4()),saved['id'])
  with self.assertRaises(DeliveryError):pr.send(self.store,Mock(),flow,saved['id'],'bad')
 def test_resume_bound_expiring_single_use_and_current_fields(self):
  flow,account,data=self.fixture();ident=pr.save(self.store,flow,account,data)['id'];token='x'*43
  with self.store.connect() as c:c.execute(sql.SQL("UPDATE {} SET token_hash=%s,token_expires=now()+interval '1 day' WHERE id=%s").format(pr.table(self.store)),(hashlib.sha256(token.encode()).hexdigest(),ident))
  with self.assertRaises(ValueError):pr.resume(self.store,flow,str(uuid.uuid4()),token)
  restored=pr.resume(self.store,flow,account,token);self.assertEqual(restored['details']['contacts'],data['contacts']);self.assertNotIn('enrollment_token',restored['details'])
  with self.assertRaises(ValueError):pr.resume(self.store,flow,account,token)
 def test_cleanup_never_deletes_orders(self):
  flow,account,data=self.fixture();ident=pr.save(self.store,flow,account,data)['id'];order=self.request('/api/events/'+flow+'/checkout/save',data,'POST')
  with self.store.connect() as c:c.execute(sql.SQL("UPDATE {} SET expires=now()-interval '1 second' WHERE id=%s").format(pr.table(self.store)),(ident,))
  self.assertEqual(pr.cleanup(self.store),1);self.assertEqual(pr.listing(self.store,flow),[])
  with self.store.connect() as c:self.assertEqual(c.execute(sql.SQL('SELECT count(*) FROM {} WHERE id=%s').format(pr.table(self.store,'registration_orders')),(order['id'],)).fetchone()[0],1)
 def test_explicit_send_once_and_unknown_is_not_retryable(self):
  flow,account,data=self.fixture();ident=pr.save(self.store,flow,account,data)['id'];review=pr.review(self.store,flow,ident);settings=Mock();settings.read.return_value={'public_url':'https://synthetic.example.test','email':{}}
  with patch.dict('os.environ',{'REGFIRE_PARTIAL_EMAIL_LIVE':'1'}),patch('confirmation_delivery.readiness',return_value=[]),patch('communications_providers.adapter_for') as adapter:
   adapter.return_value.submit.return_value={'status':'submitted','provider_id':'synthetic'}
   self.assertEqual(pr.send(self.store,settings,flow,ident,review['review_digest'])['status'],'submitted');adapter.return_value.submit.assert_called_once()
   with self.assertRaises(ValueError):pr.send(self.store,settings,flow,ident,review['review_digest'])
   args=adapter.return_value.submit.call_args.args;self.assertEqual(args[0],'synthetic@example.test');self.assertIn('#event=',args[2]);self.assertNotIn('contacts',args[2])
 def test_stale_review_cannot_send(self):
  flow,account,data=self.fixture();ident=pr.save(self.store,flow,account,data)['id'];review=pr.review(self.store,flow,ident);pr.save(self.store,flow,account,data|{'promo_code':'NEW'})
  with patch.dict('os.environ',{'REGFIRE_PARTIAL_EMAIL_LIVE':'1'}),patch('confirmation_delivery.readiness',return_value=[]),patch('communications_providers.adapter_for') as adapter:
   with self.assertRaises(ValueError):pr.send(self.store,Mock(),flow,ident,review['review_digest'])
   adapter.assert_not_called()
 def test_unknown_send_is_not_retryable_and_token_is_hashed(self):
  flow,account,data=self.fixture();ident=pr.save(self.store,flow,account,data)['id'];review=pr.review(self.store,flow,ident);settings=Mock();settings.read.return_value={'public_url':'https://synthetic.example.test','email':{}}
  with patch.dict('os.environ',{'REGFIRE_PARTIAL_EMAIL_LIVE':'1'}),patch('confirmation_delivery.readiness',return_value=[]),patch('communications_providers.adapter_for') as adapter:
   adapter.return_value.submit.side_effect=TimeoutError()
   with self.assertRaises(DeliveryError):pr.send(self.store,settings,flow,ident,review['review_digest'])
   with self.assertRaises(ValueError):pr.send(self.store,settings,flow,ident,review['review_digest'])
   adapter.return_value.submit.assert_called_once()
  with self.store.connect() as c:
   row=c.execute(sql.SQL('SELECT email_status,token_hash FROM {} WHERE id=%s').format(pr.table(self.store)),(ident,)).fetchone();self.assertEqual(row[0],'unknown');self.assertEqual(len(row[1]),64)
 def test_group_resume_excludes_every_enrollment_and_starts_primary(self):
  flow,account,data=self.fixture();other=data|{'contacts':data['contacts']|{'email':'colleague@example.test'},'enrollment_token':'never-store'}
  raw=other|dict(group_members=[data|{'enrollment_token':'never-store'},other],group_index=1,password='never-store')
  ident=pr.save(self.store,flow,account,raw)['id'];self.assertNotIn('never-store',str(pr.listing(self.store,flow)));token='z'*43
  with self.store.connect() as c:c.execute(sql.SQL("UPDATE {} SET token_hash=%s,token_expires=now()+interval '1 day' WHERE id=%s").format(pr.table(self.store)),(hashlib.sha256(token.encode()).hexdigest(),ident))
  restored=pr.resume(self.store,flow,account,token)['details'];self.assertEqual(restored['group_index'],0);self.assertEqual(restored['contacts']['email'],'synthetic@example.test');self.assertEqual(len(restored['group_members']),2)
 def test_http_account_csrf_and_organizer_boundaries(self):
  import json
  from urllib.request import Request,build_opener,ProxyHandler
  from urllib.error import HTTPError
  flow,account,data=self.fixture();opener=build_opener(ProxyHandler({}))
  def call(path,payload=None,headers=None):
   return opener.open(Request(self.url+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Origin':self.url,'Content-Type':'application/json',**(headers or {})}))
  base='/api/public/events/'+flow
  with self.assertRaises(HTTPError):call(base+'/partial-draft',data)
  with call('/api/attendee/login',dict(email='synthetic@example.test',password='Test123')) as r:cookie=r.headers['Set-Cookie'].split(';')[0]
  with call('/api/attendee/me',headers={'Cookie':cookie}) as r:csrf=json.load(r)['user']['csrf']
  with self.assertRaises(HTTPError):call(base+'/partial-draft',data,{'Cookie':cookie})
  with call(base+'/partial-draft',data,{'Cookie':cookie,'X-Attendee-CSRF':csrf}) as r:self.assertTrue(json.load(r)['saved'])
  with self.assertRaises(HTTPError):call('/api/events/'+flow+'/partial-registrations',headers={'Cookie':cookie})
  self.assertEqual(len(pr.listing(self.store,flow)),1)
