import unittest,copy
from urllib.error import HTTPError
import tests.test_events as events
from membership import starter as membership_starter
from registration import validate_page,starter

class FieldMappingTests(unittest.TestCase):
 def test_legacy_fields_opt_out_and_supported_types(self):
  page=starter({'id':'synthetic','name':'Test'})
  self.assertTrue(all(f['membership_lookup']=='' for f in validate_page(page)['fields']))
  page['fields'][2]['membership_lookup']='email'
  self.assertEqual(validate_page(page)['fields'][2]['membership_lookup'],'email')
  page['fields'][3]['membership_lookup']='member_id'
  with self.assertRaises(ValueError):validate_page(page)
 def test_duplicate_mapping_rejected_only_for_overlapping_regtypes(self):
  page=starter({'id':'synthetic','name':'Test'});page['fields'][0]['membership_lookup']='email';page['fields'][2]['membership_lookup']='email'
  with self.assertRaises(ValueError):validate_page(page)
  page['regtypes'].append({'id':'other','name':'Other','price_minor':0});page['fields'][0]['visible_to']=['other'];page['fields'][2]['visible_to']=['attendee']
  self.assertEqual(len(validate_page(page)['fields']),6)

class BackgroundMembershipTests(unittest.TestCase):
 setUp=events.PostgresTest.setUp
 tearDown=events.PostgresTest.tearDown
 start=events.PostgresTest.start
 stop=events.PostgresTest.stop
 request=events.PostgresTest.request
 auth_headers=events.PostgresTest.auth_headers
 def fixture(self):
  ev=self.request('/api/events',events.draft(),'POST');self.base='/api/events/'+ev['id'];self.page=self.request(self.base+'/registration-page');self.page['fields'][2]['membership_lookup']='email';self.request(self.base+'/registration-page',self.page,'PUT')
  self.config=membership_starter()|{'enabled':True,'source':'api','regtype_ids':['attendee'],'title':'Legacy title retained'};self.config['api']['endpoint']='fixture://demo';self.request(self.base+'/membership',self.config,'PUT');return ev
 def check(self,values,**extra):return self.request(self.base+'/membership/check-fields',{'regtype_id':'attendee','values':values,**extra},'POST')
 def test_field_mapping_persists_and_background_lookup_policies(self):
  self.fixture();self.assertEqual(self.request(self.base+'/registration-page')['fields'][2]['membership_lookup'],'email')
  self.assertEqual(self.check({'email':'active@example.test','first-name':'irrelevant'})['status'],'verified')
  self.assertFalse(self.check({'email':'inactive@example.test'})['can_continue'])
  self.assertEqual(self.check({'email':'expired@example.test'})['status'],'expired')
  self.assertFalse(self.check({'first-name':'active@example.test'})['can_continue'])
  self.config['policy']='pending';self.request(self.base+'/membership',self.config,'PUT')
  result=self.check({'email':'missing@example.test'});self.assertEqual(result['status'],'pending');self.assertTrue(result['can_continue']);self.assertIn('not confirmed',result['pricing'])
 def test_both_keys_must_match_same_record_and_hidden_field_is_ignored(self):
  self.fixture();self.page['fields'][0]['membership_lookup']='member_id'
  self.assertEqual(self.check({'email':'active@example.test','first-name':'DEMO-INACTIVE'},registration_page=self.page)['status'],'no_match')
  self.page['regtypes'].append({'id':'other','name':'Other','price_minor':0});self.page['fields'][0]['visible_to']=['other']
  self.assertEqual(self.check({'email':'active@example.test','first-name':'DEMO-INACTIVE'},registration_page=self.page)['status'],'verified')
 def test_checks_cannot_override_saved_membership_policy_and_disabled_skips_lookup(self):
  self.fixture();self.assertFalse(self.check({'email':'missing@example.test'},config={**self.config,'enabled':False})['can_continue'])
  self.config['enabled']=False;self.request(self.base+'/membership',self.config,'PUT');self.assertEqual(self.check({})['status'],'not_required')
 def test_integrations_and_membership_settings_do_not_clobber_each_other(self):
  self.fixture();old=copy.deepcopy(self.config['api']);new={**old,'credential_env':'REGFIRE_MEMBERSHIP_SYNTHETIC'}
  result=self.request(self.base+'/membership/integration',{'api':new,'expected_api':old},'POST');self.assertEqual(result['config']['title'],'Legacy title retained');self.assertTrue(result['config']['enabled'])
  policy={k:v for k,v in self.config.items() if k!='api'};policy['policy']='pending';self.request(self.base+'/membership',policy,'PUT');self.assertEqual(self.request(self.base+'/membership')['config']['api'],new)
  with self.assertRaises(HTTPError):self.request(self.base+'/membership/integration',{'api':old,'expected_api':old},'POST')
  self.assertEqual(self.check({'email':'active@example.test'})['status'],'verified')
 def test_csv_background_lookup_retains_records(self):
  self.fixture();self.config['source']='csv';self.request(self.base+'/membership',self.config,'PUT');body={'csv':'member_id,email,active,expires\nM1,member@example.test,true,2099-01-01\n','mapping':{k:k for k in ('member_id','email','active','expires')}}
  preview=self.request(self.base+'/membership/import-preview',body,'POST');self.request(self.base+'/membership/import',{**body,'digest':preview['digest'],'revision':preview['revision']},'POST')
  self.assertEqual(self.check({'email':'MEMBER@example.test'})['status'],'verified');self.assertEqual(self.request(self.base+'/membership')['import_info']['count'],1)
 def test_unassigned_client_cannot_read_or_update_connection(self):
  self.fixture();owner=self.access.session(self.raw_session);uid=self.access.save_user(owner,{'email':'client@example.test','products':['event-builder'],'event_ids':[]});code=self.access.enrollment(owner,uid);self.access.activate('client@example.test',code,self.password)
  token=self.access.login('client@example.test',self.password);self.raw_session=token;self.csrf=self.access.session(token)['csrf']
  for path,data,method in [(self.base+'/membership',None,'GET'),(self.base+'/membership/integration',{'api':self.config['api'],'expected_api':self.config['api']},'POST'),(self.base+'/membership/check-fields',{'regtype_id':'attendee','values':{'email':'active@example.test'}},'POST')]:
   with self.assertRaises(HTTPError) as error:self.request(path,data,method)
   self.assertEqual(error.exception.code,404)

if __name__=='__main__':unittest.main()
