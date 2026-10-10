import io,json,os,tempfile,unittest,uuid
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,build_opener,ProxyHandler
from urllib.error import HTTPError
from PIL import Image
from psycopg import sql
from tests.test_access import AccessTests
from tests.test_events import draft
from tests.test_photo_screening import GOOD,POLICY
from server import validate
from photo_upload import issue,upload,link_status,manage,table
from photo_screening import ScreeningUnavailable

class PhotoHTTPTests(unittest.TestCase):
 setUpAccess=AccessTests.setUp
 tearDownAccess=AccessTests.tearDown
 request=AccessTests.request
 user=AccessTests.user
 def setUp(self):
  self.setUpAccess();self.tmp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'REGFIRE_GOOGLE_VISION_API_KEY':''});self.env.start();self.keypatch=patch('photo_screening.KEY_FILE',Path(self.tmp.name)/'google-key');self.keypatch.start()
  self.server.photo_transport=lambda _:GOOD
  self.events=[self.store.save(str(uuid.uuid4()),validate(draft()|{'name':name,'photo_upload':POLICY}),datetime.now(timezone.utc).isoformat(),False) for name in ('Photo event','Other event')]
  b=io.BytesIO();Image.new('RGB',(240,320),'orange').save(b,'PNG');self.image=b.getvalue()
 def tearDown(self):
  self.keypatch.stop();self.env.stop();self.tmp.cleanup();self.tearDownAccess()
 def raw(self,path,body=b'',headers=None):
  try:
   with build_opener(ProxyHandler({})).open(Request(self.url+path,data=body,headers={'Origin':self.url,**(headers or {})})) as r:
    return r.status,json.load(r)
  except HTTPError as e:return e.code,json.load(e)
 def photo(self,token,action='status',content=None,**headers):
  return self.raw('/api/photo-upload',self.image if content is None and action=='upload' else content or b'',{'X-Photo-Token':token,'X-Photo-Action':action,'X-Photo-Consent':'google-vision','Content-Type':'image/png',**headers})
 def new(self,event=None):
  event=event or self.events[0]
  status,data,_=self.request('/api/events/'+event['id']+'/attendee-photos',{'name':'Synthetic Attendee','email':'attendee@example.test'},self.token,self.owner['csrf']);self.assertEqual(status,200,data)
  return data,data['path'].split('token=')[1]
 def test_upload_persist_reload_and_private_event_isolation(self):
  data,token=self.new();status,result=self.photo(token,'upload');self.assertEqual(status,200,result);self.assertEqual(result['status'],'approved')
  self.assertTrue(self.photo(token)[1]['approved'])
  rows=self.request('/api/events/'+self.events[0]['id']+'/attendee-photos',token=self.token)[1]['attendees'];self.assertEqual(rows[0]['id'],data['id']);self.assertNotIn(token,str(rows));self.assertEqual(self.request('/api/events/'+self.events[1]['id']+'/attendee-photos',token=self.token)[1]['attendees'],[])
  self.assertEqual(self.request('/api/events/'+self.events[0]['id']+'/attendee-photos/'+data['id'])[0],401)
  self.assertEqual(self.request('/api/events/'+self.events[1]['id']+'/attendee-photos/'+data['id'],token=self.token)[0],404)
  with self.store.connect() as c:photo=c.execute(sql.SQL('SELECT photo,screening FROM {} WHERE id=%s').format(table(self.store)),(data['id'],)).fetchone()
  with Image.open(io.BytesIO(bytes(photo[0]))) as im:self.assertEqual(im.format,'JPEG');self.assertFalse(im.getexif())
  self.assertEqual(photo[1]['face_check'],'passed');self.store.initialize();self.assertTrue(link_status(self.store,token)['approved'])
 def test_rejected_unavailable_disabled_retain_previous_photo(self):
  data,token=self.new();self.assertEqual(self.photo(token,'upload')[0],200)
  import copy
  bad=copy.deepcopy(GOOD);bad['responses'][0]['safeSearchAnnotation']['adult']='VERY_LIKELY';self.server.photo_transport=lambda _:bad
  self.assertEqual(self.photo(token,'upload')[0],400);self.assertTrue(self.photo(token)[1]['approved'])
  self.server.photo_transport=lambda _:(_ for _ in ()).throw(ScreeningUnavailable('Unavailable'))
  self.assertEqual(self.photo(token,'upload')[0],503)
  self.store.save(self.events[0]['id'],validate(draft()|{'photo_upload':dict(POLICY,enabled=False)}),datetime.now(timezone.utc).isoformat(),True)
  with patch('photo_screening.screen') as scan:self.assertEqual(self.photo(token,'upload')[0],403);scan.assert_not_called()
  self.assertFalse(self.photo(token)[1]['enabled']);self.assertEqual(self.photo(token,'upload',**{'X-Photo-Consent':''})[0],400)
 def test_invalid_token_expired_revoked_rotated_and_limits(self):
  data,token=self.new();self.assertEqual(self.photo('invalid')[0],404)
  new=manage(self.store,self.events[0]['id'],data['id'],'renew');self.assertEqual(self.photo(token)[0],404);token=new['path'].split('token=')[1]
  manage(self.store,self.events[0]['id'],data['id'],'revoke');self.assertEqual(self.photo(token,'upload')[0],404)
  data,token=self.new()
  with self.store.connect() as c:c.execute(sql.SQL("UPDATE {} SET expires=now()-interval '1 second' WHERE id=%s").format(table(self.store)),(data['id'],))
  self.assertEqual(self.photo(token)[0],404)
  data,token=self.new()
  with self.store.connect() as c:c.execute(sql.SQL('UPDATE {} SET attempts=10 WHERE id=%s').format(table(self.store)),(data['id'],))
  self.assertEqual(self.photo(token,'upload')[0],429)
 def test_validate_bytes_csrf_owner_and_event_permissions(self):
  data,token=self.new()
  for content in (b'<svg></svg>',b'not-an-image'):
   self.assertEqual(self.photo(token,'upload',content)[0],400)
  b=io.BytesIO();Image.new('RGB',(30,30)).save(b,'PNG');self.assertEqual(self.photo(token,'upload',b.getvalue())[0],400)
  b=io.BytesIO();Image.new('RGB',(200,200)).save(b,'PNG',save_all=True,append_images=[Image.new('RGB',(200,200),'red')],loop=0);self.assertEqual(self.photo(token,'upload',b.getvalue())[0],400)
  self.assertEqual(self.photo(token,'upload',**{'Origin':'https://foreign.example'})[0],403)
  self.assertEqual(self.request('/api/events/'+self.events[0]['id']+'/attendee-photos',{},self.token)[0],403)
  uid,raw,actor=self.user(['event-builder'])
  self.assertEqual(self.request('/api/events/'+self.events[0]['id']+'/attendee-photos',token=raw)[0],404)
  self.assertEqual(self.request('/api/photo-screening-config',token=raw)[0],403)
  self.assertEqual(self.request('/api/photo-screening-config',{'action':'replace','secret':'synthetic-key-000000','revision':'initial'},raw,actor['csrf'])[0],403)
 def test_private_credential_configuration_and_paid_test_support(self):
  status,result,_=self.request('/api/photo-screening-config',token=self.token);self.assertEqual(result['status'],'unconfigured')
  status,result,_=self.request('/api/photo-screening-config',{'action':'replace','secret':'synthetic-key-000000','revision':result['revision']},self.token,self.owner['csrf']);self.assertEqual(status,200,result);self.assertTrue(result['configured']);self.assertNotIn('synthetic-key',str(result));self.assertEqual((Path(self.tmp.name)/'google-key').stat().st_mode&0o777,0o600)
  with patch('photo_screening.request',return_value=GOOD) as request:
   self.assertEqual(self.request('/api/photo-screening-test',{},self.token,self.owner['csrf'])[0],400);request.assert_not_called()
   status,result,_=self.request('/api/photo-screening-test',{'confirm_paid_test':True},self.token,self.owner['csrf']);self.assertEqual(status,200,result);request.assert_called_once()
 def test_revoke_or_disable_during_scan_cannot_save(self):
  data,token=self.new()
  def revoke(_):manage(self.store,self.events[0]['id'],data['id'],'revoke');return GOOD
  self.server.photo_transport=revoke;self.assertEqual(self.photo(token,'upload')[0],409)
  data,token=self.new()
  def disable(_):self.store.save(self.events[0]['id'],validate(draft()|{'photo_upload':dict(POLICY,enabled=False)}),datetime.now(timezone.utc).isoformat(),True);return GOOD
  self.server.photo_transport=disable;self.assertEqual(self.photo(token,'upload')[0],409)
  with self.store.connect() as c:self.assertEqual(c.execute(sql.SQL('SELECT count(*) FROM {} WHERE photo IS NOT NULL').format(table(self.store))).fetchone()[0],0)
