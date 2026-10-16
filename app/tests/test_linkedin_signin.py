import unittest,uuid,secrets
from unittest.mock import patch
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
from urllib.parse import parse_qs,urlsplit
from psycopg import sql
import test_checkout as tc
from test_linkedin_http import NoRedirect
import publication,linkedin_signin as ls,attendee_accounts as aa
class LinkedInSignIn(unittest.TestCase):
 setUp=tc.CheckoutStorage.setUp;tearDown=tc.CheckoutStorage.tearDown;start=tc.CheckoutStorage.start;stop=tc.CheckoutStorage.stop;request=tc.CheckoutStorage.request;auth_headers=tc.CheckoutStorage.auth_headers;setup_order=tc.CheckoutStorage.setup_order
 def flow(self):
  flow,_,_=self.setup_order(0);v=publication.state(self.store,flow);publication.state(self.store,flow,dict(published=True,revision=v['revision'],review_digest=v['review_digest']));return flow
 def claims(self,subject='subject1',address='social@example.test'):return dict(subject=subject,email=address,email_verified=True)
 def test_verified_identity_required_and_linked_login_preserves_address(self):
  flow=self.flow()
  with self.assertRaises(ValueError):ls.complete(self.store,flow,self.claims()|{'email_verified':False})
  first=ls.complete(self.store,flow,self.claims());again=ls.complete(self.store,flow,self.claims(address='changed@example.test'));self.assertEqual(again['email'],first['email'])
  with self.store.connect() as c:self.assertEqual(c.execute(sql.SQL('SELECT count(*) FROM {}').format(aa.table(self.store,'attendee_social_identities'))).fetchone()[0],1)
 def test_existing_email_needs_fresh_password_auth_and_no_email_only_link(self):
  flow=self.flow();account=str(uuid.uuid4());token=secrets.token_urlsafe(32)
  with self.store.connect() as c:
   c.execute(sql.SQL('INSERT INTO {}(id,email,password_hash) VALUES(%s,%s,%s)').format(aa.table(self.store,'attendee_accounts')),(account,'social@example.test',aa.password_hash('Test123')))
  with self.assertRaisesRegex(ValueError,'existing attendee'):ls.complete(self.store,flow,self.claims())
  with self.store.connect() as c:c.execute(sql.SQL("INSERT INTO {}(token_hash,account_id,csrf,authenticated_at) VALUES(%s,%s,'synthetic',now()-interval '16 minutes')").format(aa.table(self.store,'attendee_sessions')),(aa.digest(token),account))
  proof=dict(session_hash=aa.digest(token),account_id=account)
  with self.assertRaises(ValueError):ls.complete(self.store,flow,self.claims(),proof)
  with self.store.connect() as c:c.execute(sql.SQL('UPDATE {} SET authenticated_at=now() WHERE token_hash=%s').format(aa.table(self.store,'attendee_sessions')),(aa.digest(token),))
  self.assertEqual(ls.complete(self.store,flow,self.claims(),proof)['email'],'social@example.test')
 def test_http_published_only_disabled_default_session_cookie_no_organizer_grants(self):
  flow=self.flow();opener=build_opener(ProxyHandler({}),NoRedirect());env={'REGFIRE_LINKEDIN_CLIENT_ID':'synthetic','REGFIRE_LINKEDIN_CLIENT_SECRET':'synthetic-secret','REGFIRE_LINKEDIN_REDIRECT_URI':self.url+'/api/linkedin/callback'}
  with patch.dict('os.environ',env):
   with opener.open(self.url+'/api/linkedin/status?purpose=signin') as r:self.assertIn(b'false',r.read())
  env['REGFIRE_LINKEDIN_SIGNIN_ENABLED']='1'
  with patch.dict('os.environ',env):
   with self.assertRaises(HTTPError) as redirect:opener.open(self.url+'/api/linkedin/start?purpose=signin&flow='+flow+'&request='+str(uuid.uuid4()))
   self.assertEqual(redirect.exception.code,303);headers=redirect.exception.headers;state=parse_qs(urlsplit(headers['Location']).query)['state'][0];cookie=headers['Set-Cookie'].split(';')[0]
   with patch('linkedin_import.profile_from_code',return_value=self.claims()|{'given_name':'Synthetic'}):
    with opener.open(Request(self.url+'/api/linkedin/callback?state='+state+'&code=synthetic',headers={'Cookie':cookie})) as r:
     body=r.read().decode();cookies=r.headers.get_all('Set-Cookie');self.assertIn('enrollment_token',body);self.assertNotIn('synthetic-secret',body)
   attendee=next(x.split(';')[0] for x in cookies if x.startswith('regfire_attendee_'))
   with opener.open(Request(self.url+'/api/attendee/me',headers={'Cookie':attendee})) as r:self.assertIn(b'social@example.test',r.read())
   with self.assertRaises(HTTPError) as denied:opener.open(Request(self.url+'/api/events',headers={'Cookie':attendee}))
   self.assertEqual(denied.exception.code,401)
 def test_unpublished_flow_cannot_issue_session(self):
  flow,_,_=self.setup_order(0)
  with self.assertRaises(ValueError):ls.complete(self.store,flow,self.claims())
