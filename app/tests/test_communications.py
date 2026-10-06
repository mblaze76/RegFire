import json, os, secrets, stat, tempfile, unittest
from pathlib import Path
from unittest.mock import patch, Mock
import test_access
from access import AccessError
from communications_settings import Settings
from communications_providers import SendGridAdapter, TwilioAdapter, DeliveryError, RecoveryTransport
from password_recovery import PasswordRecovery

def payload(settings):
 return {'action':'save','revision':settings.public()['revision'],'public_url':'https://accounts.example.test','email':{'provider':'sendgrid','sender':'accounts@example.test','sender_name':'RegFire','secret_action':'replace','secret':'SG.synthetic-private-key-0123456789'},'sms':{'provider':'twilio','account_sid':'AC'+'0'*32,'sender':'+15555550100','secret_action':'replace','secret':'synthetic-private-token-0123456789'}}

class ConfigTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.settings=Settings(Path(self.tmp.name)/'private'/'communications.json')
 def tearDown(self):self.tmp.cleanup()
 def test_private_storage_keep_clear_stale_and_redaction(self):
  data=payload(self.settings);result=self.settings.save(data)
  self.assertTrue(result['email']['secret_stored']);self.assertTrue(result['sms']['secret_stored'])
  for channel in ('email','sms'):self.assertNotIn(data[channel]['secret'],json.dumps(result))
  self.assertEqual(stat.S_IMODE(self.settings.path.stat().st_mode),0o600);self.assertEqual(stat.S_IMODE(self.settings.path.parent.stat().st_mode),0o700)
  with self.assertRaises(AccessError):self.settings.save(data)
  data=payload(self.settings);data['email']['secret_action']='keep';data['email']['secret']='';data['sms']['secret_action']='clear';self.settings.save(data)
  self.assertEqual(self.settings.read()['email']['api_key'],'SG.synthetic-private-key-0123456789');self.assertEqual(self.settings.read()['sms']['auth_token'],'')
  self.assertTrue(Settings(self.settings.path).public()['email']['secret_stored'])
 def test_invalid_input_atomic_and_private_permissions(self):
  self.settings.save(payload(self.settings));old=self.settings.path.read_bytes()
  for channel,key,value in [('sms','account_sid','not-a-sid'),('sms','sender','555-0100'),('email','sender','x\r\nBcc:test@example.test'),('email','secret','secret\nvalue-12345678'),('email','provider','unknown')]:
   data=payload(self.settings);data[channel][key]=value
   with self.assertRaises(AccessError):self.settings.save(data)
   self.assertEqual(old,self.settings.path.read_bytes())
  for origin in ('https://user:secret@example.test','http://remote.example.test'):
   data=payload(self.settings);data['public_url']=origin
   with self.assertRaises(AccessError):self.settings.save(data)
   self.assertEqual(old,self.settings.path.read_bytes())
  self.settings.path.chmod(0o644)
  with self.assertRaises(AccessError):self.settings.public()
 def test_recovery_delivery_gate(self):
  self.settings.save(payload(self.settings));mailer=RecoveryTransport(self.settings)
  with patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'0'}),patch('communications_providers.HTTPSClient.request') as network:
   self.assertFalse(mailer.configured)
   with self.assertRaises(DeliveryError):mailer.send('person@example.test','https://accounts.example.test/login#reset=test')
   network.assert_not_called()
  with patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'1'}),patch('communications_providers.HTTPSClient.request',return_value=(202,{'X-Message-Id':'synthetic'},b'')) as network:
   self.assertTrue(mailer.configured);mailer.send('person@example.test','https://accounts.example.test/login#reset=test')
   self.assertIn('30 minutes',json.loads(network.call_args.args[1])['content'][0]['value'])
 def test_legacy_smtp_preserved(self):
  mailer=RecoveryTransport(self.settings)
  with patch('password_recovery.SMTPMailer') as smtp:
   smtp.return_value.configured=True;smtp.return_value.base_url='https://old.example.test'
   self.assertTrue(mailer.configured);self.assertEqual(mailer.base_url,'https://old.example.test');mailer.send('person@example.test','link');smtp.return_value.send.assert_called_once_with('person@example.test','link')

class AdapterTests(unittest.TestCase):
 def test_sendgrid_twilio_payloads_and_safe_errors(self):
  client=Mock();client.request.return_value=(202,{'X-Message-Id':'sg-test'},b'')
  result=SendGridAdapter({'sender':'from@example.test','sender_name':'RegFire','api_key':'synthetic'},client).submit('to@example.test','Subject','Body')
  self.assertEqual(result,{'status':'submitted','provider_id':'sg-test'});self.assertEqual(client.request.call_args.args[0],'https://api.sendgrid.com/v3/mail/send')
  client.request.return_value=(201,{},b'{"sid":"SMsynthetic"}');adapter=TwilioAdapter({'account_sid':'AC'+'0'*32,'auth_token':'synthetic','sender':'+15555550100'},client)
  self.assertEqual(adapter.submit('+15555550101','','Hello')['status'],'submitted');self.assertIn(b'To=%2B15555550101',client.request.call_args.args[1])
  client.request.return_value=(400,{},b'{"error":"private detail"}')
  with self.assertRaises(DeliveryError) as exc:adapter.submit('+15555550101','','Hello')
  self.assertNotIn('private detail',str(exc.exception))

class CommunicationsHTTPTests(unittest.TestCase):
 request=test_access.AccessTests.request
 user=test_access.AccessTests.user
 def setUp(self):
  test_access.AccessTests.setUp(self);self.tmp=tempfile.TemporaryDirectory();self.server.communications_settings_path=Path(self.tmp.name)/'private'/'communications.json';self.settings=Settings(self.server.communications_settings_path)
 def tearDown(self):
  if hasattr(self.server,'recovery'):self.server.recovery.close()
  test_access.AccessTests.tearDown(self);self.tmp.cleanup()
 def test_owner_only_and_csrf(self):
  url='/api/admin/communications';self.assertEqual(self.request(url)[0],401)
  uid,raw,user=self.user(['event-builder']);self.assertEqual(self.request(url,token=raw)[0],403)
  self.a.save_user(self.owner,{'email':'person@example.test','role':'admin','status':'active','products':['event-builder']});admin=self.a.login('person@example.test',self.password)
  for path in [url,'/communications','/communications.js','/communications.css']:self.assertEqual(self.request(path,token=admin)[0],403)
  self.assertEqual(self.request(url,token=self.token)[0],200)
  self.assertEqual(self.request(url,payload(self.settings),self.token)[0],403)
  self.assertEqual(self.request(url,payload(self.settings),self.token,self.owner['csrf'],origin=False)[0],403)
 def test_save_validate_persistence_and_no_secret_echo(self):
  url='/api/admin/communications';data=payload(self.settings)
  with patch('communications_providers.HTTPSClient.request',side_effect=AssertionError('No provider access')):
   status,result,_=self.request(url,data,self.token,self.owner['csrf']);self.assertEqual(status,200);self.assertTrue(result['email']['secret_stored']);self.assertFalse(result['delivery_enabled'])
   status,checked,_=self.request(url,{'action':'validate'},self.token,self.owner['csrf']);self.assertEqual(status,200);self.assertIn('No provider connection',checked['message'])
  for channel in ('email','sms'):self.assertNotIn(data[channel]['secret'],json.dumps(result))
  self.assertEqual(self.request(url,data,self.token,self.owner['csrf'])[0],409);self.assertEqual(Settings(self.settings.path).public()['revision'],result['revision'])
  audit=str(self.a.audit_rows(self.owner));self.assertIn('communications_settings_updated',audit);self.assertNotIn(data['email']['secret'],audit)
  self.assertFalse(self.request('/api/auth/me')[1]['recovery_available']);self.assertIsNotNone(self.a.session(self.token))
 def test_future_schema_rejects_cross_event_audience_links(self):
  import uuid
  from psycopg import sql, errors
  from psycopg.types.json import Jsonb
  first,second,audience,campaign=[str(uuid.uuid4()) for _ in range(4)]
  def table(name):return sql.Identifier(self.store.schema,name)
  with self.store.connect() as c:
   for event in (first,second):c.execute(sql.SQL('INSERT INTO {}(id,body,updated) VALUES(%s,%s,now())').format(self.store.table()),(event,Jsonb({})))
   c.execute(sql.SQL('INSERT INTO {}(id,event_id,name,recipients) VALUES(%s,%s,%s,%s)').format(table('comm_audiences')),(audience,first,'Synthetic',Jsonb([])))
   with self.assertRaises(errors.ForeignKeyViolation):
    with c.transaction():c.execute(sql.SQL('INSERT INTO {}(id,event_id,created_by,audience_id,name,channel,subject,body) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)').format(table('comm_campaigns')),(campaign,second,self.owner_id,audience,'Synthetic','email','Test','Test'))
 def test_recovery_tokens_owner_protection_with_new_adapter(self):
  self.user();self.settings.save(payload(self.settings))
  with patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'1'}),patch('communications_providers.HTTPSClient.request',return_value=(202,{'X-Message-Id':'synthetic'},b'')) as send:
   r=PasswordRecovery(self.a,RecoveryTransport(self.settings));self.server.recovery=r
   r.request('person@example.test','synthetic');r.request('owner@example.test','synthetic');r.jobs.join();self.assertEqual(send.call_count,1)
   text=json.loads(send.call_args.args[1])['content'][0]['value'];token=text.split('#reset=')[1].split()[0]
   r.complete(token,secrets.token_urlsafe(24),'synthetic')
   with self.assertRaises(AccessError):r.complete(token,secrets.token_urlsafe(24),'synthetic')
   self.assertIsNotNone(self.a.session(self.token))

if __name__=='__main__':unittest.main()
