import json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import Mock, patch
from communications_settings import Settings
from communications_providers import BirdEmailAdapter, BirdSMSAdapter, DeliveryError, RecoveryTransport
from access import AccessError
KEY='bk_us1_synthetic_private_0123456789'
class BirdTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.settings=Settings(Path(self.tmp.name)/'private'/'communications.json');self.client=Mock();self.client.request.return_value=(202,{},b'{"id":"sms_synthetic","status":"accepted"}')
 def tearDown(self):self.tmp.cleanup()
 def payload(self):
  return {'revision':self.settings.public()['revision'],'public_url':'https://accounts.example.test','email':{'provider':'bird','sender':'accounts@example.test','sender_name':'RegFire','secret_action':'replace','secret':KEY},'sms':{'provider':'bird','sender':'+15555550100','secret_action':'replace','secret':KEY}}
 def test_storage_and_placeholder(self):
  self.assertEqual(self.settings.public()['sms']['provider'],'bird');saved=self.settings.save(self.payload());self.assertNotIn(KEY,json.dumps(saved));self.assertFalse(saved['email']['issues']);self.assertEqual(Settings(self.settings.path).public(),saved)
  before=self.settings.path.read_bytes();p=self.payload();p['sms']['secret']='bk_xxxxxxxxx'
  with self.assertRaises(AccessError):self.settings.save(p)
  self.assertEqual(self.settings.path.read_bytes(),before)
  p=self.payload();p['sms']['secret_action']='clear';self.assertFalse(self.settings.save(p)['sms']['secret_stored'])
 def test_switch_clears_old_credentials(self):
  self.settings.save(self.payload());p=self.payload();p['email'].update(provider='sendgrid',secret_action='keep');p['sms'].update(provider='twilio',secret_action='keep',account_sid='AC'+'0'*32)
  result=self.settings.save(p);self.assertFalse(result['email']['secret_stored']);self.assertFalse(result['sms']['secret_stored'])
 def test_disabled_and_placeholder_do_not_send(self):
  with patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'0'}):
   with self.assertRaises(DeliveryError):BirdSMSAdapter({'auth_token':KEY},self.client).submit_otp('+15555550101','493021')
  with patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'1'}):
   with self.assertRaises(DeliveryError):BirdSMSAdapter({'auth_token':'bk_xxxxxxxxx'},self.client).submit_otp('+15555550101','493021')
  self.client.request.assert_not_called()
 @patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'1'})
 def test_requests_and_regions(self):
  adapter=BirdSMSAdapter({'auth_token':KEY,'sender':'+15555550100'},self.client);self.assertEqual(adapter.submit_otp('+15555550101','493021')['status'],'submitted')
  url,body,headers=self.client.request.call_args.args;self.assertEqual(url,'https://us1.platform.bird.com/v1/sms/messages');self.assertEqual(headers['Authorization'],'Bearer '+KEY)
  self.assertEqual(json.loads(body),{'to':'+15555550101','template':{'slug':'bird_otp_verification','parameters':{'code':'493021'}}})
  adapter.submit('+15555550101','','Welcome',category='service');self.assertEqual(json.loads(self.client.request.call_args.args[1])['category'],'service')
  BirdEmailAdapter({'api_key':KEY.replace('us1','eu1'),'sender':'accounts@example.test','sender_name':'RegFire'},self.client).submit('person@example.test','Subject','Body')
  url,body,_=self.client.request.call_args.args;self.assertEqual(url,'https://eu1.platform.bird.com/v1/email/messages');self.assertEqual(json.loads(body)['text'],'Body')
 @patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'1'})
 def test_errors_redacted(self):
  for status,body in [(400,b'{"error":"private secret"}'),(202,b'[]'),(202,b'invalid'),(202,b'{"id":"x","status":"failed"}'),(202,b'{"status":"accepted"}')]:
   self.client.request.return_value=(status,{},body)
   with self.assertRaises(DeliveryError) as exc:BirdSMSAdapter({'auth_token':KEY},self.client).submit_otp('+15555550101','493021')
   self.assertNotIn('private secret',str(exc.exception))
 @patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'1'})
 def test_recovery(self):
  self.settings.save(self.payload());mailer=RecoveryTransport(self.settings);self.assertTrue(mailer.configured)
  with patch('communications_providers.HTTPSClient.request',return_value=(202,{},b'{"id":"em_synthetic","status":"accepted"}')) as network:
   mailer.send('person@example.test','https://accounts.example.test/login#reset=synthetic');self.assertIn('/v1/email/messages',network.call_args.args[0]);self.assertIn('30 minutes',json.loads(network.call_args.args[1])['text'])
