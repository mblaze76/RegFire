import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_events
from test_events import draft
class Flows(unittest.TestCase):
    setUp=test_events.PostgresTest.setUp
    start=test_events.PostgresTest.start
    stop=test_events.PostgresTest.stop
    tearDown=test_events.PostgresTest.tearDown
    auth_headers=test_events.PostgresTest.auth_headers
    request=test_events.PostgresTest.request
    def test_migration_isolation_order_restart_and_shared_event(self):
        event=self.request('/api/events',draft(),'POST');base='/api/events/'+event['id'];page=self.request(base+'/registration-page');page['intro']='Existing attendee content';saved=self.request(base+'/registration-page',page,'PUT')
        self.store.initialize()
        flows=self.request(base+'/flows');self.assertEqual([(f['id'],f['name']) for f in flows],[(event['id'],'Attendee')]);self.assertEqual(self.request(base+'/registration-page'),saved)
        flows=self.request(base+'/flows',{'name':'Test exhibitor','kind':'exhibitor'},'POST');child=flows[-1]['id'];childbase='/api/events/'+child
        second=self.request(childbase+'/registration-page');second['intro']='Independent exhibitor content';self.request(childbase+'/registration-page',second,'PUT')
        self.assertEqual(self.request(base+'/registration-page'),saved);self.assertEqual(len(self.request('/api/events')),1)
        self.request(base+'/flows',{'action':'rename','id':child,'name':'Partners'},'POST');self.request(base+'/flows',{'action':'reorder','ids':[child,event['id']]},'POST')
        self.request(base,event|{'venue':'Shared venue update'},'PUT');model=self.request(childbase+'/flow-preview');self.assertEqual(model['event']['venue'],'Shared venue update');self.assertEqual(model['registration']['intro'],'Independent exhibitor content')
        self.stop();self.start();self.assertEqual(self.request(base+'/flows')[0]['name'],'Partners');self.assertEqual(self.request(base+'/registration-page'),saved)

    def test_remove_flow_confirmation_isolation_and_restart(self):
        event=self.request('/api/events',draft(),'POST');base='/api/events/'+event['id']
        before=self.request(base+'/registration-page')
        flows=self.request(base+'/flows',{'name':'Temporary removal test','kind':'custom'},'POST');child=flows[-1]['id']
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError):self.request(base+'/flows',{'action':'remove','id':child,'confirm_name':'wrong'},'POST')
        remaining=self.request(base+'/flows',{'action':'remove','id':child,'confirm_name':'Temporary removal test'},'POST')
        self.assertEqual([f['name'] for f in remaining],['Attendee'])
        with self.assertRaises(HTTPError) as error:self.request('/api/events/'+child+'/flow-preview')
        self.assertEqual(error.exception.code,404)
        self.store.initialize();self.stop();self.start()
        self.assertEqual(len(self.request(base+'/flows')),1);self.assertEqual(self.request(base+'/registration-page'),before)
        self.request(base+'/flows',{'action':'remove','id':event['id'],'confirm_name':'Attendee'},'POST')
        self.store.initialize();self.assertEqual(self.request(base+'/flows'),[])
        self.request(base,event,'PUT');self.assertEqual(self.request(base+'/flows'),[])
        self.assertEqual(len(self.request('/api/events')),1)

    def test_registrant_entry_validates_context_without_admin_login(self):
        event=self.request('/api/events',draft(),'POST')
        from urllib.request import Request,build_opener,ProxyHandler
        from urllib.error import HTTPError
        import json
        with build_opener(ProxyHandler({})).open(self.url+'/api/registrant-event?event='+event['id']) as response:
            self.assertEqual(json.load(response),{'event_id':event['id']})
        with self.assertRaises(HTTPError):build_opener(ProxyHandler({})).open(self.url+'/api/registrant-event?event=bad')
