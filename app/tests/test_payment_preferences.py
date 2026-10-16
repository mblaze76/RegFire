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

 def test_manual_tax_quote_and_clear(self):
  import uuid
  flow,_,data=self.setup_order();base='/api/events/'+flow;path=base+'/checkout/preferences'
  extra=self.request(base+'/extra-options');ident=str(uuid.uuid4());extra['items']=[dict(id=ident,name='Synthetic taxable item',description='',kind='physical',price_minor=105,inventory=10,variants=[],allow_multiple=True,taxable=True)];self.request(base+'/extra-options',extra,'PUT');data['extras']=[dict(item_id=ident,quantity=1)]
  self.assertTrue(self.request(base+'/checkout/quote',data,'POST')['tax_pending'])
  prefs=self.request(path);tax=dict(rate_bps=825,jurisdiction='Synthetic jurisdiction',source='Synthetic test only',confirmed=True)
  saved=self.request(path,prefs|{'tax':tax},'POST');q=self.request(base+'/checkout/quote',data,'POST');self.assertEqual(q['tax_minor'],9);self.assertFalse(q['tax_pending'])
  legacy={k:v for k,v in saved.items() if k!='tax'};saved=self.request(path,legacy,'POST');self.assertEqual(saved['tax'],tax)
  saved=self.request(path,saved|{'tax':None},'POST');self.assertTrue(self.request(base+'/checkout/quote',data,'POST')['tax_pending'])
  with self.assertRaises(HTTPError):self.request(base+'/checkout/save',data,'POST')
  self.request(path,saved|{'tax':tax|{'rate_bps':0}},'POST');self.assertEqual(self.request(base+'/checkout/quote',data,'POST')['tax_minor'],0)
 def test_manual_tax_validation(self):
  tax=dict(rate_bps=700,jurisdiction='Synthetic',source='Test',confirmed=True)
  for change in [{'rate_bps':True},{'rate_bps':-1},{'rate_bps':10001},{'rate_bps':7.5},{'confirmed':False},{'source':''},{'jurisdiction':'x'*201},{'secret':'x'}]:
   with self.assertRaises(ValueError):pp.validate(pp.DEFAULT|{'tax':tax|change})
