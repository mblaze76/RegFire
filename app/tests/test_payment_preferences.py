import unittest
from urllib.error import HTTPError
import test_checkout as tc
import payment_preferences as pp
class Preferences(unittest.TestCase):
 setUp=tc.CheckoutStorage.setUp;tearDown=tc.CheckoutStorage.tearDown;start=tc.CheckoutStorage.start;stop=tc.CheckoutStorage.stop;request=tc.CheckoutStorage.request;auth_headers=tc.CheckoutStorage.auth_headers;setup_order=tc.CheckoutStorage.setup_order
 def test_saved_flow_isolation_stale_and_no_connections(self):
  a,_,_=self.setup_order();b,_,_=self.setup_order();path='/api/events/'+a+'/checkout/preferences'
  first=self.request(path);saved=self.request(path,first|{'processor':'other','methods':['card','invoice'],'cards':['visa']},'POST')
  self.assertEqual(saved['revision'],1);self.assertEqual(self.request('/api/events/'+a+'/checkout/methods')['preferences']['methods'],['card','invoice'])
  self.assertEqual(self.request('/api/events/'+b+'/checkout/preferences')['processor'],'undecided')
  self.assertEqual(self.request('/api/events/'+a+'/checkout/methods')['methods'],[])
  with self.assertRaises(HTTPError):self.request(path,first,'POST')
  with self.assertRaises(HTTPError):self.request(path,saved|{'secret':'do-not-store'},'POST')
  self.stop();self.start();self.assertEqual(self.request(path)['processor'],'other')
 def test_validation(self):
  for change in [{'processor':'bad'},{'methods':[]},{'cards':['unknown']},{'methods':['card','card']},{'secret':'x'}]:
   with self.assertRaises(ValueError):pp.validate(pp.DEFAULT|change)
