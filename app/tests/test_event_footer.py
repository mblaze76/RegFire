import unittest
import test_events
from test_events import draft
from registration import starter
from event_footer import normalize
from psycopg import sql
from psycopg.types.json import Jsonb
from urllib.error import HTTPError

class FooterPersistence(unittest.TestCase):
    setUp=test_events.PostgresTest.setUp;tearDown=test_events.PostgresTest.tearDown;start=test_events.PostgresTest.start;stop=test_events.PostgresTest.stop;request=test_events.PostgresTest.request;auth_headers=test_events.PostgresTest.auth_headers
    def legacy(self,event,footer):
        page=starter(event);page.setdefault('appearance',{})['footer']=footer
        with self.store.connect() as c:
            c.execute(sql.SQL('INSERT INTO {}(event_id,body,updated) VALUES(%s,%s,CURRENT_TIMESTAMP) ON CONFLICT(event_id) DO UPDATE SET body=excluded.body').format(self.store.page_table()),(event['id'],Jsonb(page)))
    def test_migrate_share_preserve_and_stale_old_flow_save(self):
        event=self.request('/api/events',draft(),'POST');base='/api/events/'+event['id']
        child=next(f for f in self.request(base+'/flows',dict(name='Exhibitor',kind='exhibitor'),'POST') if f['id']!=event['id'])
        original=dict(enabled=True,heading='Need help?',message='Original text',hours='9–5',links='Help | https://example.test/help',facebook='https://example.test/social')
        self.legacy(event,original)
        state=self.request(base+'/event-footer');self.assertFalse(state['conflict']);self.assertEqual(state['footer'],normalize(original))
        childpath='/api/events/'+child['id']+'/registration-page';page=self.request(childpath);self.assertEqual(page['appearance']['footer'],normalize(original))
        state['footer']['message']='Shared edit';saved=self.request(base+'/event-footer',state,'PUT')
        self.assertEqual(saved['legacy'][0]['footer']['message'],'Original text')
        # An already-open older flow editor cannot overwrite the shared footer.
        result=self.request(childpath,page,'PUT');self.assertEqual(result['appearance']['footer']['message'],'Shared edit')
        self.assertEqual(self.request(base+'/registration-page')['appearance']['footer']['hours'],'9–5')
        with self.assertRaises(HTTPError):self.request(base+'/event-footer',state,'PUT')
        self.stop();self.start();self.assertEqual(self.request(base+'/event-footer'),saved)
        with self.assertRaises(HTTPError):self.request(base+'/event-footer',dict(revision=saved['revision'],footer=dict(enabled=True,links='Bad | javascript:alert(1)')),'PUT')
    def test_conflicting_legacy_requires_explicit_choice(self):
        event=self.request('/api/events',draft(),'POST');base='/api/events/'+event['id']
        flow=next(f for f in self.request(base+'/flows',dict(name='Press',kind='media'),'POST') if f['id']!=event['id'])
        self.legacy(event,dict(enabled=True,message='Attendee support'))
        self.legacy(dict(id=flow['id'],name='Press'),dict(enabled=True,message='Press support'))
        state=self.request(base+'/event-footer');self.assertTrue(state['conflict']);self.assertEqual(len(state['legacy']),2)
        self.assertEqual(self.request('/api/events/'+flow['id']+'/registration-page')['appearance']['footer']['message'],'Press support')
        with self.assertRaises(HTTPError):self.request(base+'/event-footer',state,'PUT')
        state.update(footer=state['legacy'][0]['footer'],resolve_conflict=True)
        saved=self.request(base+'/event-footer',state,'PUT');self.assertFalse(saved['conflict']);self.assertEqual(len(saved['legacy']),2)
        self.assertEqual(self.request('/api/events/'+flow['id']+'/registration-page')['appearance']['footer'],saved['footer'])

    upload=test_events.PostgresTest.upload
    def test_footer_style_logo_flow_ownership_and_restart(self):
        event=self.request('/api/events',draft(),'POST');base='/api/events/'+event['id']
        other=self.request('/api/events',draft(),'POST')
        logo=self.upload(event['id'],'logo');foreign=self.upload(other['id'],'logo')
        state=self.request(base+'/event-footer')
        state['footer'].update(enabled=True,font='default',color='#abcdef',logo_asset_id=logo['id'],message='Keep this copy')
        saved=self.request(base+'/event-footer',state,'PUT')
        flow=next(f for f in self.request(base+'/flows',dict(name='Staff',kind='custom'),'POST') if f['id']!=event['id'])
        path='/api/events/'+flow['id']+'/registration-page'
        page=self.request(path)
        self.assertEqual(page['appearance']['footer'],saved['footer'])
        self.assertEqual(self.request(path,page,'PUT')['appearance']['footer'],saved['footer'])
        self.stop();self.start();self.assertEqual(self.request(base+'/event-footer'),saved)
        for invalid in [dict(logo_asset_id=foreign['id']),dict(color='red'),dict(font='nonexistent')]:
            bad=dict(saved,footer={**saved['footer'],**invalid})
            with self.assertRaises(HTTPError):self.request(base+'/event-footer',bad,'PUT')
            self.assertEqual(self.request(base+'/event-footer'),saved)
        saved['footer']['logo_asset_id']=None
        removed=self.request(base+'/event-footer',saved,'PUT')
        self.assertIsNone(removed['footer']['logo_asset_id'])
        self.assertEqual(removed['footer']['message'],'Keep this copy')
