import unittest, secrets, threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import test_access
from access import AccessError, digest, Access
from password_recovery import PasswordRecovery, SMTPMailer, GENERIC

class FakeMailer:
 configured=True
 errors=[]
 base_url='https://accounts.example.test'
 def __init__(self):self.messages=[];self.fail=False
 def send(self,address,link):
  if self.fail:raise RuntimeError('private provider detail')
  self.messages.append((address,link))

class RecoveryTests(unittest.TestCase):
 setUp=test_access.AccessTests.setUp
 request=test_access.AccessTests.request
 user=test_access.AccessTests.user
 def tearDown(self):
  if hasattr(self.server,'recovery'):self.server.recovery.close()
  test_access.AccessTests.tearDown(self)
 def service(self):
  self.mail=FakeMailer();self.r=PasswordRecovery(self.a,self.mail);self.server.recovery=self.r;return self.r
 def issue(self):
  self.r.request('person@example.test','test');self.r.jobs.join()
  return self.mail.messages[-1][1].split('#reset=')[1]
 def test_reset_revokes_sessions_all_links_and_manual_codes(self):
  uid,raw,user=self.user();self.service();manual=self.a.enrollment(self.owner,uid);token=self.issue();second=self.issue()
  self.assertFalse(user['email_verified']);self.assertIsNotNone(self.a.session(raw))
  with self.store.connect() as c:
   stored=c.execute(self.a.q('SELECT token_hash FROM {}','password_resets')).fetchall()
   self.assertIn((digest(token),),stored);self.assertNotIn((token,),stored)
  new=secrets.token_urlsafe(24);self.r.complete(token,new,'test')
  self.assertIsNone(self.a.session(raw))
  for link in (token,second):
   with self.assertRaises(AccessError):self.r.complete(link,new,'test')
  with self.assertRaises(AccessError):self.a.activate('person@example.test',manual,new)
  with self.assertRaises(AccessError):self.a.login('person@example.test',self.password)
  self.assertTrue(self.a.session(self.a.login('person@example.test',new))['email_verified'])
  audit=str(self.a.audit_rows(self.owner));self.assertNotIn(token,audit);self.assertIn('password_reset_completed',audit)
 def test_generic_http_and_no_mail_for_ineligible_accounts(self):
  self.user();self.service()
  self.a.save_user(self.owner,{'email':'assigned@example.test'})
  self.a.save_user(self.owner,{'email':'suspended@example.test','status':'suspended'})
  for address in ('person@example.test','missing@example.test','owner@example.test','assigned@example.test','suspended@example.test','invalid'):
   status,body,_=self.request('/api/auth/forgot-password',{'email':address});self.assertEqual((status,body),(200,{'message':GENERIC}))
  self.r.jobs.join();self.assertEqual(len(self.mail.messages),1)
  recipient,link=self.mail.messages[0];self.assertEqual(recipient,'person@example.test');self.assertTrue(link.startswith('https://accounts.example.test/login#reset='));self.assertNotIn('?',link)
  self.assertEqual(self.request('/api/auth/forgot-password',{'email':recipient},origin=False)[0],403)
  self.assertEqual(self.request('/api/auth/reset-password',{'token':'invalid','password':self.password},origin=False)[0],403)
 def test_expiry_status_change_and_admin_code_invalidate_links(self):
  uid,raw,user=self.user();self.service();token=self.issue()
  with self.store.connect() as c:c.execute(self.a.q("UPDATE {} SET expires=now()-interval '1 second'",'password_resets'))
  with self.assertRaises(AccessError):self.r.complete(token,self.password,'test')
  token=self.issue();self.a.enrollment(self.owner,uid)
  with self.assertRaises(AccessError):self.r.complete(token,self.password,'test')
  token=self.issue();self.a.save_user(self.owner,{'email':'person@example.test','status':'suspended'})
  with self.assertRaises(AccessError):self.r.complete(token,self.password,'test')
 def test_mail_failure_and_unconfigured_do_not_change_account(self):
  uid,raw,user=self.user();self.service();self.mail.fail=True
  self.assertEqual(self.r.request('person@example.test','test'),GENERIC);self.r.jobs.join()
  with self.store.connect() as c:self.assertEqual(c.execute(self.a.q('SELECT count(*) FROM {}','password_resets')).fetchone()[0],0)
  self.assertIsNotNone(self.a.session(raw));self.assertIn('password_reset_email_failed',str(self.a.audit_rows(self.owner)))
  off=PasswordRecovery(self.a,SMTPMailer({}));self.assertEqual(off.request('person@example.test','test'),GENERIC);self.assertIsNone(off.worker);self.assertFalse(off.status()['configured'])
 def test_rate_limits_persist_and_do_not_block_login(self):
  self.user();self.service()
  for _ in range(5):self.r.request('person@example.test','test')
  self.r.jobs.join();self.assertEqual(len(self.mail.messages),3)
  other=PasswordRecovery(Access(self.store),self.mail)
  for _ in range(15):other.request('nobody@example.test','test')
  with self.assertRaises(AccessError) as exc:other.request('person@example.test','test')
  self.assertEqual(exc.exception.status,429)
  self.assertIsNotNone(self.a.login('person@example.test',self.password));other.close()
 def test_concurrent_redeem_only_one_succeeds(self):
  self.user();self.service();token=self.issue()
  def redeem(_):
   try:self.r.complete(token,secrets.token_urlsafe(24),'test');return True
   except AccessError:return False
  with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sorted(pool.map(redeem,range(2))),[False,True])
 def test_http_completion_clears_cookie_and_admin_status_is_private(self):
  self.user();self.service();token=self.issue()
  status,body,headers=self.request('/api/auth/reset-password',{'token':token,'password':secrets.token_urlsafe(24)})
  self.assertEqual(status,200);self.assertIn('Max-Age=0',headers['Set-Cookie'])
  self.assertEqual(self.request('/api/admin/users')[0],401)
  self.assertTrue(self.request('/api/admin/users',token=self.token)[1]['recovery']['configured'])
  self.assertTrue(self.request('/api/auth/me')[1]['recovery_available'])
 def test_admin_reset_authority_and_stale_role(self):
  uid,raw,user=self.user();self.service()
  self.a.save_user(self.owner,{'email':'person@example.test','role':'admin','status':'active'})
  admin=self.a.session(self.a.login('person@example.test',self.password))
  other=self.a.save_user(self.owner,{'email':'admin2@example.test','role':'admin'})
  for target in (uid,self.owner_id,other):
   with self.assertRaises(AccessError):self.a.enrollment(admin,target)
  client=self.a.save_user(self.owner,{'email':'client@example.test'})
  self.assertTrue(self.a.enrollment(admin,client))
  self.a.save_user(self.owner,{'email':'person@example.test','role':'client','status':'active'})
  with self.assertRaises(AccessError):self.a.enrollment(admin,client)
  with self.assertRaises(AccessError):self.a.enrollment(self.owner,self.owner_id)
 def test_password_policy_invalid_token_and_no_premature_verification(self):
  uid,raw,user=self.user();self.service();token=self.issue()
  with self.assertRaises(AccessError):self.r.complete(token,'short','test')
  with self.assertRaises(AccessError):self.r.complete('x'*43,self.password,'test')
  self.assertFalse(self.a.session(raw)['email_verified'])
  self.r.complete(token,self.password,'test')

class SMTPConfigurationTests(unittest.TestCase):
 def config(self,**changes):
  env={'REGFIRE_SMTP_HOST':'smtp.example.test','REGFIRE_SMTP_FROM':'accounts@example.test','REGFIRE_PUBLIC_URL':'https://accounts.example.test'};env.update(changes);return SMTPMailer(env)
 def test_configuration_rejects_unsafe_origins_and_plaintext(self):
  self.assertTrue(self.config().configured)
  for url in ('http://example.test','https://user:pass@example.test','https://example.test/path','https://example.test?x=1','https://example.test#reset=x'):
   self.assertFalse(self.config(REGFIRE_PUBLIC_URL=url).configured)
  self.assertTrue(self.config(REGFIRE_PUBLIC_URL='http://127.0.0.1:8766').configured)
  self.assertFalse(self.config(REGFIRE_SMTP_SECURITY='none').configured)
  self.assertFalse(self.config(REGFIRE_SMTP_PORT='invalid').configured)
  self.assertFalse(self.config(REGFIRE_SMTP_USERNAME='user').configured)
 def test_starttls_before_credentials_and_message_contents(self):
  mailer=self.config(REGFIRE_SMTP_SECURITY='starttls',REGFIRE_SMTP_USERNAME='user',REGFIRE_SMTP_PASSWORD='synthetic-password')
  with patch('password_recovery.smtplib.SMTP') as factory:
   smtp=factory.return_value.__enter__.return_value
   mailer.send('test@example.test','https://accounts.example.test/login#reset=synthetic')
   calls=[c[0] for c in smtp.method_calls];self.assertLess(calls.index('starttls'),calls.index('login'))
   message=smtp.send_message.call_args.args[0];self.assertEqual(message['To'],'test@example.test');self.assertIn('30 minutes',message.get_content())

if __name__=='__main__':unittest.main()
