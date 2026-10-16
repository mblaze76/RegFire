import unittest,json
from urllib.request import urlopen
from urllib.error import HTTPError
import test_events
from test_events import draft
import publication
from event_entry import model

class EventEntry(unittest.TestCase):
 setUp=test_events.PostgresTest.setUp;tearDown=test_events.PostgresTest.tearDown;start=test_events.PostgresTest.start;stop=test_events.PostgresTest.stop;request=test_events.PostgresTest.request;auth_headers=test_events.PostgresTest.auth_headers
 def test_sibling_entry_and_publication_boundary(self):
  event=self.request('/api/events',draft(),'POST')['id']
  base='/api/events/'+event
  for name,kind in [('Exhibitor Registration','exhibitor'),('Press Registration','media')]:self.request(base+'/flows',dict(action='create',name=name,kind=kind),'POST')
  flows=self.request(base+'/flows');self.assertGreaterEqual(len(flows),3)
  for flow in flows:
   result=self.request('/api/events/'+flow['id']+'/event-welcome')
   self.assertEqual(result['event_id'],event)
   self.assertEqual([f['id'] for f in result['flows']],[f['id'] for f in flows])
  a,b=flows[:2]
  page=self.request(base+'/welcome-page');page['about']='Published welcome';self.request(base+'/welcome-page',page,'PUT')
  for f in (a,b):
   v=publication.state(self.store,f['id']);publication.state(self.store,f['id'],dict(published=True,revision=v['revision'],review_digest=v['review_digest']))
  page=self.request(base+'/welcome-page');page['about']='PRIVATE unsaved publication draft';self.request(base+'/welcome-page',page,'PUT')
  result=model(self.store,a['id'],public=True)
  self.assertEqual(result['page']['about'],'Published welcome')
  self.assertEqual({f['id'] for f in result['flows']},{a['id'],b['id']})
  self.assertNotIn('PRIVATE',str(result))
  with urlopen(self.url+'/api/public/events/'+a['id']+'/event-welcome') as response:self.assertEqual(json.load(response)['page']['about'],'Published welcome')
  with self.assertRaises(HTTPError):urlopen(self.url+'/api/public/events/'+flows[2]['id']+'/event-welcome')
  with urlopen(self.url+'/welcome') as response:self.assertEqual(response.status,200)
  v=publication.state(self.store,b['id']);publication.state(self.store,b['id'],dict(published=False,revision=v['revision']))
  self.assertEqual([f['id'] for f in model(self.store,a['id'],public=True)['flows']],[a['id']])
