import unittest,uuid,io
from PIL import Image
import test_events
from test_events import draft
from test_sessions import session
from sessions import validate,import_preview
from membership import validate as membership_validate,starter
from urllib.error import HTTPError

class ProfilesValidation(unittest.TestCase):
    def test_speaker_relationships_and_cancellation(self):
        speaker=dict(id=str(uuid.uuid4()),first_name='Avery',last_name='Morgan',bio='Bio',role='Host',organization='Example',photo_asset_id=None)
        row=session(speaker_ids=[speaker['id']],credits=1.25,status='canceled',cancellation_note='Unavailable')
        result=validate(dict(sessions=[row],speakers=[speaker]),draft())
        self.assertEqual(result['sessions'][0]['status'],'canceled')
        self.assertEqual(result['speakers'][0]['bio'],'Bio')
        for change in [dict(speaker_ids=['missing']),dict(status='removed')]:
            with self.assertRaises(ValueError):validate(dict(sessions=[row|change],speakers=[speaker]),draft())
        self.assertEqual(validate(dict(sessions=[session()]),draft())['sessions'][0]['status'],'active')
    def test_import_status_and_legacy_blank_mapping(self):
        content='title,date,start_time,end_time,credits,status,cancellation_note\nWorkshop,2026-11-18,09:00,10:00,1.5,canceled,Unavailable\n'
        mapping={k:k for k in ('title','date','start_time','end_time','credits','status','cancellation_note')}
        result=import_preview(dict(content=content,mapping=mapping),draft()|dict(id=str(uuid.uuid4())),'USD')
        self.assertEqual(result['errors'],[]);self.assertEqual(result['sessions'][0]['status'],'canceled');self.assertEqual(result['sessions'][0]['credits'],1.5)
        event=draft()|dict(id=str(uuid.uuid4()));legacy={k:k for k in ('title','date','start_time','end_time')}
        old=import_preview(dict(content=content,mapping=legacy),event,'USD')
        new=import_preview(dict(content=content,mapping=legacy|dict(credits='',status='',cancellation_note='')),event,'USD')
        self.assertEqual(old['sessions'][0]['id'],new['sessions'][0]['id'])
    def test_membership_styles(self):
        c=starter()|dict(title='Welcome members',details='Enter your ID.',title_font='georgia',details_font='arial',title_color='#A60000',details_color='#24242a')
        self.assertEqual(membership_validate(c,[])['title_color'],'#a60000')
        self.assertEqual(membership_validate(c|dict(title=''),[])['title'],'Verify your membership')
        for change in [dict(title_font='bad'),dict(details_color='red'),dict(details='x'*3001)]:
            with self.assertRaises(ValueError):membership_validate(c|change,[])

class ProfilesStorage(unittest.TestCase):
    setUp=test_events.PostgresTest.setUp;tearDown=test_events.PostgresTest.tearDown;start=test_events.PostgresTest.start;stop=test_events.PostgresTest.stop;request=test_events.PostgresTest.request;auth_headers=test_events.PostgresTest.auth_headers
    def test_profiles_credits_status_photo_and_flow_membership(self):
        event=self.request('/api/events',draft(),'POST');base='/api/events/'+event['id'];flows=self.request(base+'/flows',dict(name='Press',kind='media'),'POST');child=next(f['id'] for f in flows if f['name']=='Press');other='/api/events/'+child
        speaker=dict(id=str(uuid.uuid4()),first_name='Avery',last_name='Morgan',bio='Sample biography',role='Speaker',organization='Example',photo_asset_id=None)
        page=self.request(base+'/sessions');page['speakers']=[speaker];page['sessions']=[session(speaker_ids=[speaker['id']],credits=2.5,status='canceled',cancellation_note='Canceled by organizer')]
        saved=self.request(base+'/sessions',page,'PUT');self.assertEqual(saved['sessions'][0]['credits'],2.5)
        self.assertEqual(self.request(other+'/sessions')['speakers'],[])
        saved['sessions'][0]['status']='active';saved=self.request(base+'/sessions',saved,'PUT')
        self.stop();self.start();self.assertEqual(self.request(base+'/sessions'),saved)
        invalid=saved|dict(speakers=[speaker|dict(photo_asset_id=str(uuid.uuid4()))])
        with self.assertRaises(HTTPError):self.request(base+'/sessions',invalid,'PUT')
        cfg=starter()|dict(title='Member welcome',details='Use your ID',title_font='georgia',details_font='arial',title_color='#a60000',details_color='#555c68')
        self.request(other+'/membership',cfg,'PUT');self.assertEqual(self.request(other+'/membership')['config']['title'],'Member welcome');self.assertEqual(self.request(base+'/membership')['config']['title'],'Verify your membership')
        self.stop();self.start();self.assertEqual(self.request(other+'/membership')['config'],cfg)
