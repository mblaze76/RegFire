import unittest,uuid,json,io,tempfile,os
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler
from psycopg import sql
from psycopg.types.json import Jsonb
import test_checkout as tc
import confirmation,wallet,confirmation_delivery

class ConfirmationValidation(unittest.TestCase):
 def test_layout_qr_payload_and_limits(self):
  p=confirmation.validate({});self.assertEqual(p['layout'],confirmation.BLOCKS)
  for data in [dict(layout=['receipt']),dict(qr_position='absolute'),dict(show_wallet='yes'),dict(heading=''),dict(sponsors=[dict(asset_id='bad')])]:
   with self.assertRaises((ValueError,AttributeError)):confirmation.validate(data)
  encoded=json.loads(confirmation.qr_payload('event','confirmation'));self.assertEqual(encoded,dict(event_id='event',confirmation_id='confirmation'));self.assertEqual(len(encoded),2)
 def test_wallet_private_storage_and_sample_gate(self):
  with tempfile.TemporaryDirectory() as d:
   settings=wallet.Settings(Path(d)/'wallet.json');data=settings.public();data['google'].update(service_account_action='replace',service_account='synthetic invalid JSON');saved=settings.save(data);self.assertNotIn('synthetic',json.dumps(saved));self.assertEqual(settings.path.stat().st_mode&0o777,0o600);self.assertTrue(saved['google']['stored']['service_account'])
   data=saved;data['google']['enabled']=True
   with self.assertRaises(ValueError):settings.save(data)
  with self.assertRaises(ValueError):wallet.pass_data(dict(sample=True),{})

class ConfirmationStorage(unittest.TestCase):
 setUp=tc.CheckoutStorage.setUp;tearDown=tc.CheckoutStorage.tearDown;start=tc.CheckoutStorage.start;stop=tc.CheckoutStorage.stop;request=tc.CheckoutStorage.request;auth_headers=tc.CheckoutStorage.auth_headers;setup_order=tc.CheckoutStorage.setup_order
 def test_persistence_preview_isolation_and_stale_revision(self):
  flow,_,_=self.setup_order();other,_,_=self.setup_order();base='/api/events/'+flow+'/confirmation';page=self.request(base);page.update(heading='See you there',layout=['message','attendee','sessions','receipt','extras','sponsors'],qr_position='left')
  preview=self.request(base+'/preview',page,'POST');self.assertEqual(preview['settings']['qr_position'],'left');self.assertEqual(self.request(base)['qr_position'],'right')
  saved=self.request(base,page,'PUT');self.assertEqual(saved['revision'],1)
  with self.assertRaises(HTTPError):self.request(base,page,'PUT')
  self.stop();self.start();self.assertEqual(self.request(base)['heading'],'See you there');self.assertEqual(self.request('/api/events/'+other+'/confirmation')['heading'],confirmation.DEFAULT['heading'])
  with self.assertRaises(HTTPError):self.request(base,saved|dict(sponsors=[dict(asset_id=str(uuid.uuid4()),name='Foreign')]),'PUT')
 def test_verified_order_pdf_and_actual_ids(self):
  flow,_,data=self.setup_order(0);order=self.request('/api/events/'+flow+'/checkout/save',data,'POST');path='/api/checkout/'+order['id']+'/confirmation'
  with self.assertRaises(HTTPError):self.request(path)
  self.request('/api/checkout/'+order['id']+'/start',{},'POST');doc=self.request(path);self.assertFalse(doc['sample']);self.assertEqual(doc['paid_minor'],0);self.assertEqual(json.loads(doc['qr_payload']),{'event_id':flow,'confirmation_id':order['id']});self.assertIsNone(doc['wallet']['apple']);self.assertIsNone(doc['wallet']['google'])
  req=Request(self.url+path+'/receipt.pdf',headers=self.auth_headers())
  with build_opener(ProxyHandler({})).open(req) as response:raw=response.read();self.assertEqual(response.headers['Content-Type'],'application/pdf');self.assertTrue(raw.startswith(b'%PDF'))
  with self.store.connect() as c:
   self.assertEqual(c.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(self.schema,'confirmation_delivery'))).fetchone()[0],1)
   c.execute(sql.SQL("UPDATE {} SET body=jsonb_set(body,'{{actor_id}}',to_jsonb(%s::text)) WHERE id=%s").format(sql.Identifier(self.schema,'registration_orders')),(str(uuid.uuid4()),order['id']))
  with self.assertRaises(HTTPError):self.request(path)
 def test_owner_only_provider_settings_and_no_sending(self):
  flow,_,_=self.setup_order();self.server.wallet_settings_path=Path(self.upload_tmp.name)/'wallet.json';self.server.communications_settings_path=Path(self.upload_tmp.name)/'communications.json'
  self.assertFalse(self.request('/api/admin/wallet')['apple']['enabled']);self.assertIn('disabled',' '.join(self.request('/api/admin/communications')['confirmation_issues']))
  actor=self.access.session(self.raw_session)['id']
  with self.store.connect() as c:c.execute(sql.SQL("UPDATE {} SET role='admin' WHERE id=%s").format(sql.Identifier(self.schema,'access_users')),(actor,))
  for path in ['/api/admin/wallet','/wallet-settings','/api/admin/communications']:
   with self.assertRaises(HTTPError) as caught:self.request(path)
   self.assertEqual(caught.exception.code,403)
 def test_wallet_event_selection_isolated_and_read_only(self):
  flow,_,data=self.setup_order(0);other,_,_=self.setup_order(0)
  self.server.wallet_settings_path=Path(self.upload_tmp.name)/'wallet.json'
  order=self.request('/api/events/'+flow+'/checkout/save',data,'POST')
  self.request('/api/checkout/'+order['id']+'/start',{},'POST')
  before=self.request('/api/admin/wallet')
  selected=self.request('/api/admin/wallet/event?event='+flow)
  self.assertEqual([r['id'] for r in selected['registrations']],[order['id']])
  self.assertEqual(self.request('/api/admin/wallet/event?event='+other)['registrations'],[])
  self.assertEqual(self.request('/api/admin/wallet'),before)
  for query in ['event=invalid','event='+other+'&order='+order['id']+'&provider=apple','event='+flow+'&order='+order['id']+'&provider=apple']:
   with self.assertRaises(HTTPError) as caught:self.request('/api/admin/wallet/pass?'+query)
   self.assertIn(caught.exception.code,(400,404))
  actor=self.access.session(self.raw_session)['id']
  with self.store.connect() as c:c.execute(sql.SQL("UPDATE {} SET role='admin' WHERE id=%s").format(sql.Identifier(self.schema,'access_users')),(actor,))
  with self.assertRaises(HTTPError) as caught:self.request('/api/admin/wallet/event?event='+flow)
  self.assertEqual(caught.exception.code,403)
 def test_outbox_submission_unknown_never_retries(self):
  flow,_,data=self.setup_order(0);order=self.request('/api/events/'+flow+'/checkout/save',data,'POST');self.request('/api/checkout/'+order['id']+'/start',{},'POST')
  from communications_settings import Settings
  settings=Settings(Path(self.upload_tmp.name)/'email.json');cfg=settings.public();cfg.update(public_url='https://regfire.example');cfg['email'].update(provider='sendgrid',sender='events@regfire.example',sender_name='RegFire',secret_action='replace',secret='synthetic_test_secret');settings.save(cfg)
  with self.assertRaises(Exception):confirmation_delivery.dispatch(self.store,settings,order['id'])
  with patch.dict(os.environ,{'REGFIRE_CONFIRMATION_EMAIL_LIVE':'1','REGFIRE_COMMUNICATIONS_LIVE':'1'}),patch('confirmation_delivery.adapter_for') as adapter:
   adapter.return_value.submit.side_effect=TimeoutError()
   with self.assertRaises(Exception):confirmation_delivery.dispatch(self.store,settings,order['id'])
   with self.assertRaises(Exception):confirmation_delivery.dispatch(self.store,settings,order['id'])
   self.assertEqual(adapter.return_value.submit.call_count,1)
  with self.store.connect() as c:self.assertEqual(c.execute(sql.SQL('SELECT status FROM {} WHERE order_id=%s').format(sql.Identifier(self.schema,'confirmation_delivery')),(order['id'],)).fetchone()[0],'unknown')
 def test_long_pdf_paginates_without_clipping(self):
  flow,_,_=self.setup_order();doc=confirmation.document(self.store,flow);doc['quote']['lines']*=60;doc['settings']['qr_position']='bottom'
  from confirmation_pdf import render
  raw=render(doc,self.store,Path(self.upload_tmp.name));self.assertTrue(raw.startswith(b'%PDF'));self.assertGreater(len(raw),15000)

class WalletSigning(unittest.TestCase):
 def test_google_claims_and_apple_archive_with_isolated_signer(self):
  # Synthetic in-memory signing material only. No account or usable provider credential is created.
  from datetime import datetime,timedelta,timezone
  from cryptography import x509
  from cryptography.x509.oid import NameOID
  from cryptography.hazmat.primitives.asymmetric import rsa
  from cryptography.hazmat.primitives import hashes,serialization
  import zipfile,hashlib,jwt
  key=rsa.generate_private_key(public_exponent=65537,key_size=2048);now=datetime.now(timezone.utc);subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Synthetic test signer')]);cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(1).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).sign(key,hashes.SHA256())
  doc=dict(sample=False,sandbox=False,status='confirmed_free',event_id=str(uuid.uuid4()),confirmation_id=str(uuid.uuid4()),event=dict(name='Synthetic test event',start='Nov 18, 2026',venue='Test hall'),quote=dict(regtype='Attendee',details=[dict(label='Name',value='Jordan Sample')]))
  doc['qr_payload']=confirmation.qr_payload(doc['event_id'],doc['confirmation_id'])
  with patch('wallet.issues',return_value=[]),patch('wallet.apple_material',return_value=(cert,key,cert)):
   raw=wallet.apple_pass(doc,dict(pass_type='pass.synthetic',team_id='TESTTEAM00',organization='Synthetic only'))
  with zipfile.ZipFile(io.BytesIO(raw)) as archive:
   manifest=json.loads(archive.read('manifest.json'));self.assertTrue(archive.read('signature'))
   for name,digest in manifest.items():self.assertEqual(hashlib.sha1(archive.read(name)).hexdigest(),digest)
   payload=json.loads(archive.read('pass.json'));self.assertEqual(payload['barcodes'][0]['message'],doc['qr_payload']);self.assertEqual(payload['serialNumber'],doc['confirmation_id'])
  pem=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode();account=dict(type='service_account',client_email='test@synthetic.iam.gserviceaccount.com',private_key=pem)
  cfg=dict(enabled=True,issuer_id='123',class_id='123.synthetic',service_account=json.dumps(account));url=wallet.google_url(doc,cfg);claims=jwt.decode(url.rsplit('/',1)[1],key.public_key(),algorithms=['RS256'],audience='google');obj=claims['payload']['genericObjects'][0];self.assertEqual(obj['barcode']['value'],doc['qr_payload']);self.assertEqual(obj['textModulesData'][0]['body'],'Jordan Sample')
  for changed in [dict(sample=True),dict(sandbox=True),dict(status='pending')]:
   with self.assertRaises(ValueError):wallet.google_url(doc|changed,cfg)
