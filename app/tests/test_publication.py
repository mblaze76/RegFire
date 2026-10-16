import unittest
from urllib.error import HTTPError
import test_checkout as tc
import publication
class Publication(unittest.TestCase):
 setUp=tc.CheckoutStorage.setUp;tearDown=tc.CheckoutStorage.tearDown;start=tc.CheckoutStorage.start;stop=tc.CheckoutStorage.stop;request=tc.CheckoutStorage.request;auth_headers=tc.CheckoutStorage.auth_headers;setup_order=tc.CheckoutStorage.setup_order
 def test_publish_unpublish_isolation_and_revision(self):
  a,_,_=self.setup_order();b,_,_=self.setup_order();url='/api/events/'+a+'/publication'
  first=self.request(url);self.assertFalse(first['published']);self.assertFalse(first['hosted']);self.assertFalse(publication.enabled(self.store,a))
  v=self.request(url,dict(published=True,revision=0,review_digest=publication.state(self.store,a)['review_digest']),'POST');self.assertTrue(v['available']);self.assertIn('/register#event='+a,v['url']);self.assertFalse(publication.enabled(self.store,b))
  with self.assertRaises(HTTPError):self.request(url,dict(published=False,revision=0),'POST')
  self.stop();self.start();self.assertTrue(self.request(url)['published']);self.request(url,dict(published=False,revision=v['revision']),'POST');self.assertFalse(publication.enabled(self.store,a))
 def test_production_requires_host_enable(self):
  from unittest.mock import patch
  a,_,_=self.setup_order();publication.state(self.store,a,dict(published=True,revision=0,review_digest=publication.state(self.store,a)['review_digest']))
  with patch.dict('os.environ',{'REGFIRE_ENV':'production','REGFIRE_PUBLICATION_ENABLED':'0'}):self.assertFalse(publication.enabled(self.store,a))
