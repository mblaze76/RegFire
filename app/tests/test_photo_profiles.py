import unittest
from unittest.mock import patch
from tests.test_attendee_photos import PhotoHTTPTests
import photo_profiles as profiles
from photo_screening import ScreeningUnavailable
from access import AccessError

class ProfileTests(unittest.TestCase):
 setUp=PhotoHTTPTests.setUp
 tearDown=PhotoHTTPTests.tearDown
 setUpAccess=PhotoHTTPTests.setUpAccess
 tearDownAccess=PhotoHTTPTests.tearDownAccess
 request=PhotoHTTPTests.request
 user=PhotoHTTPTests.user
 raw=PhotoHTTPTests.raw
 photo=PhotoHTTPTests.photo
 new=PhotoHTTPTests.new
 def test_reuse_masked_metadata_and_clear(self):
  model=profiles.listing(self.store)
  self.assertNotIn('synthetic-key',str(model))
  self.assertEqual(profiles.resolve(self.store,self.events[0]['id']),profiles.resolve(self.store,self.events[1]['id']))
  p=next(p for p in model['profiles'] if p['name']=='Synthetic connection')
  profiles.save(self.store,dict(p,name='Renamed',secret_action='clear'))
  for e in self.events:
   with self.assertRaises(ScreeningUnavailable):profiles.resolve(self.store,e['id'])
 def test_reassignment_is_event_scoped_and_stale_writes_rejected(self):
  other=profiles.save(self.store,{'name':'Second','secret_action':'replace','secret':'other-synthetic-key'})
  data={'event_id':self.events[0]['id'],'profile_id':other['id'],'revision':1}
  profiles.assign(self.store,data)
  self.assertEqual(profiles.resolve(self.store,self.events[0]['id'])[0],'other-synthetic-key')
  self.assertEqual(profiles.resolve(self.store,self.events[1]['id'])[0],'synthetic-key-000000')
  with self.assertRaises(AccessError):profiles.assign(self.store,data)
  profiles.assign(self.store,dict(data,profile_id='',revision=2))
  self.store.initialize()
  with self.assertRaises(ScreeningUnavailable):profiles.resolve(self.store,self.events[0]['id'])
 def test_client_cannot_read_write_provider_or_manage_photos(self):
  uid,raw,actor=self.user(['event-builder'])
  self.a.save_user(self.owner,{'email':'person@example.test','status':'active','products':['event-builder'],'event_ids':[self.events[0]['id']]})
  raw=self.a.login('person@example.test',self.password);actor=self.a.session(raw)
  for path in ['/api/photo-profiles','/api/photo-screening-config','/api/events/'+self.events[0]['id']+'/attendee-photos']:
   self.assertEqual(self.request(path,token=raw)[0],403,path)
  self.assertEqual(self.request('/api/photo-profiles',{'name':'Bad'},raw,actor['csrf'])[0],403)
  status,data,_=self.request('/api/photo-screening-status?event='+self.events[0]['id'],token=raw)
  self.assertEqual(status,200);self.assertNotIn('synthetic',str(data));self.assertNotIn('profile',str(data))
  self.assertEqual(self.request('/api/photo-screening-status?event='+self.events[1]['id'],token=raw)[0],404)
 def test_invalid_profile_input_and_revision(self):
  for data in [{'name':[]},{'name':'x','provider':'custom'},{'name':'x','secret_action':'replace','secret':'bad key'}]:
   self.assertEqual(self.request('/api/photo-profiles',data,self.token,self.owner['csrf'])[0],400)
  p=next(p for p in profiles.listing(self.store)['profiles'] if p['name']=='Synthetic connection')
  profiles.save(self.store,dict(p,name='Changed'))
  with self.assertRaises(AccessError):profiles.save(self.store,dict(p,name='Stale'))
 def test_profile_change_during_screening_prevents_approval(self):
  _,token=self.new()
  p=next(p for p in profiles.listing(self.store)['profiles'] if p['name']=='Synthetic connection')
  from tests.test_photo_screening import GOOD
  def change(_):
   profiles.save(self.store,dict(p,name='Changed',secret_action='replace',secret='replacement-synthetic-key'))
   return GOOD
  self.server.photo_transport=change
  self.assertEqual(self.photo(token,'upload')[0],409)
  self.assertFalse(self.photo(token)[1]['approved'])
 def test_unassigned_fails_before_provider(self):
  profiles.assign(self.store,{'event_id':self.events[0]['id'],'profile_id':'','revision':1})
  _,token=self.new()
  with patch('photo_screening.screen') as scan:
   self.assertEqual(self.photo(token,'upload')[0],503);scan.assert_not_called()

 def test_selected_profile_test_requires_consent_and_uses_only_its_key(self):
  p=next(p for p in profiles.listing(self.store)['profiles'] if p['name']=='Synthetic connection')
  from tests.test_photo_screening import GOOD
  data={'profile_id':p['id'],'revision':p['revision']}
  with patch('photo_screening.request',return_value=GOOD) as request:
   self.assertEqual(self.request('/api/photo-screening-test',data,self.token,self.owner['csrf'])[0],400);request.assert_not_called()
   self.assertEqual(self.request('/api/photo-screening-test',dict(data,confirm_paid_test=True),self.token,self.owner['csrf'])[0],200)
   self.assertEqual(request.call_args.args[1],'synthetic-key-000000')
