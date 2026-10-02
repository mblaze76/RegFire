import unittest,uuid,secrets,threading,json,sys
from pathlib import Path
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from database import Store,CONFIG
from access import Access,AccessError,password_ok,password_hash,digest
from server import Handler,ThreadingHTTPServer
from psycopg import sql

@unittest.skipUnless(CONFIG.exists(),'PostgreSQL required')
class AccessTests(unittest.TestCase):
 def setUp(self):
  self.store=Store(schema='regfire_access_test_'+uuid.uuid4().hex);self.store.initialize();self.a=Access(self.store)
  self.password=secrets.token_urlsafe(24);self.owner_id=self.a.bootstrap('owner@example.test',self.password);self.token=self.a.login('OWNER@example.test',self.password);self.owner=self.a.session(self.token)
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.store=self.store;self.server.access=self.a;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.server.server_port)
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join()
  with self.store.connect() as c:c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.store.schema)))
 def request(self,path,data=None,token=None,csrf=None,origin=True):
  headers={'Content-Type':'application/json'}
  if origin:headers['Origin']=self.url
  if token:headers['Cookie']='regfire_session_'+str(self.server.server_port)+'='+token
  if csrf:headers['X-CSRF-Token']=csrf
  request=Request(self.url+path,headers=headers,data=json.dumps(data).encode() if data is not None else None)
  try:
   with build_opener(ProxyHandler({})).open(request) as r:return r.status,json.load(r),r.headers
  except HTTPError as e:return e.code,json.load(e),e.headers
 def user(self,products=None):
  uid=self.a.save_user(self.owner,{'email':'person@example.test','products':products or [],'status':'assigned'})
  code=self.a.enrollment(self.owner,uid);self.a.activate('person@example.test',code,self.password)
  raw=self.a.login('person@example.test',self.password);return uid,raw,self.a.session(raw)
 def test_anonymous_cannot_read_or_write_events_or_admin(self):
  for path in ['/api/events','/api/admin/users','/api/address-config','/api/timezones']:
   self.assertEqual(self.request(path)[0],401)
  self.assertEqual(self.request('/api/events',{'name':'unauthorized'})[0],401)
 def test_product_and_admin_authorization_and_revocation(self):
  uid,raw,user=self.user(['event-builder'])
  self.assertEqual(self.request('/api/events',token=raw)[0],200)
  self.assertEqual(self.request('/api/admin/users',token=raw)[0],403)
  self.assertEqual(self.request('/api/admin/products',{'slug':'hack','name':'Hack'},raw,user['csrf'])[0],403)
  self.a.save_user(self.owner,{'email':'person@example.test','status':'active','products':[]})
  self.assertIsNone(self.a.session(raw))
  fresh=self.a.login('person@example.test',self.password)
  self.assertEqual(self.request('/api/events',token=fresh)[0],403)
 def test_csrf_and_missing_origin_rejected(self):
  data={'email':'new@example.test','products':[]}
  self.assertEqual(self.request('/api/admin/users',data,self.token)[0],403)
  self.assertEqual(self.request('/api/admin/users',data,self.token,self.owner['csrf'],False)[0],403)
  self.assertEqual(self.request('/api/admin/users',data,self.token,self.owner['csrf'])[0],200)
 def test_enrollment_is_single_use_and_not_email_verification(self):
  uid=self.a.save_user(self.owner,{'email':'person@example.test','products':['event-builder']});code=self.a.enrollment(self.owner,uid)
  with self.assertRaises(AccessError):self.a.activate('other@example.test',code,self.password)
  self.a.activate('person@example.test',code,self.password)
  with self.assertRaises(AccessError):self.a.activate('person@example.test',code,self.password)
  user=self.a.session(self.a.login('person@example.test',self.password));self.assertFalse(user['email_verified'])
 def test_owner_protected_and_bootstrap_cannot_repeat(self):
  with self.assertRaises(AccessError):self.a.bootstrap('attacker@example.test',self.password)
  with self.assertRaises(AccessError):self.a.save_user(self.owner,{'email':'owner@example.test','status':'suspended','products':[]})
 def test_suspended_and_expired_sessions_blocked(self):
  uid,raw,user=self.user(['event-builder'])
  with self.store.connect() as c:c.execute(self.a.q("UPDATE {} SET expires=now()-interval '1 second' WHERE token_hash=%s",'sessions'),(digest(raw),))
  self.assertIsNone(self.a.session(raw))
  self.a.save_user(self.owner,{'email':'person@example.test','status':'suspended','products':['event-builder']})
  with self.assertRaises(AccessError):self.a.login('person@example.test',self.password)
 def test_future_products_and_disabled_grants(self):
  self.a.save_product(self.owner,{'slug':'future-test','name':'Test registry only','enabled':True})
  uid,raw,user=self.user(['event-builder','future-test']);self.assertIn('future-test',user['products'])
  self.assertFalse(next(p for p in self.a.products() if p['slug']=='future-test')['available'])
  self.a.save_product(self.owner,{'slug':'event-builder','name':'Event builder','enabled':False})
  self.assertEqual(self.request('/api/events',token=raw)[0],403)
 def test_login_cookie_and_logout(self):
  status,body,headers=self.request('/api/auth/login',{'email':'owner@example.test','password':self.password})
  self.assertEqual(status,200);cookie=headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
  self.assertNotIn(self.password,json.dumps(body))
  self.assertEqual(self.request('/api/auth/logout',{},self.token,self.owner['csrf'])[0],200);self.assertIsNone(self.a.session(self.token))
 def test_admin_cannot_promote_or_change_owner(self):
  uid,raw,user=self.user();self.a.save_user(self.owner,{'email':'person@example.test','role':'admin','status':'active','products':[]})
  admin=self.a.session(self.a.login('person@example.test',self.password))
  with self.assertRaises(AccessError):self.a.save_user(admin,{'email':'other@example.test','role':'admin','products':[]})
 def test_private_setup_is_pinned_single_use_and_not_public_signup(self):
  import tempfile,owner_setup
  from unittest.mock import patch
  with self.store.connect() as c:c.execute(self.a.q('DELETE FROM {}','users'))
  with tempfile.TemporaryDirectory() as tmp:
   policy=Path(tmp)/'policy.json';policy.write_text(json.dumps({'email':'reserved@example.test'}));policy.chmod(0o600)
   tokenfile=Path(tmp)/'token.json'
   with patch.object(owner_setup,'POLICY',policy),patch.object(owner_setup,'TOKEN',tokenfile):
    owner_setup.prepare(self.a);code=json.loads(tokenfile.read_text())['token']
    self.assertEqual(self.request('/api/auth/setup',{'token':'invalid','password':self.password})[0],403)
    self.assertEqual(self.request('/api/auth/setup',{'token':code,'password':self.password,'email':'attacker@example.test'})[0],200)
    self.assertFalse(tokenfile.exists())
    self.assertEqual(self.a.session(self.a.login('reserved@example.test',self.password))['role'],'owner')
    self.assertEqual(self.request('/api/auth/setup',{'token':code,'password':self.password})[0],409)
 def test_password_hash_and_invalid_password(self):
  value=password_hash(self.password);self.assertNotIn(self.password,value);self.assertTrue(password_ok(self.password,value));self.assertFalse(password_ok('wrongpassword12',value))
if __name__=='__main__':unittest.main()
