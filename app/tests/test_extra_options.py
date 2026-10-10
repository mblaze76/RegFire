import unittest,uuid
import test_events
from test_events import draft
from urllib.error import HTTPError
from extra_options import validate,quote

def item(**kw):return dict(id=str(uuid.uuid4()),name='Conference shirt',description='',kind='physical',price_minor=2500,inventory=5,variants=[],allow_multiple=True,taxable=True)|kw
class ExtrasValidation(unittest.TestCase):
 def test_validation(self):
  for kw in [dict(inventory=-1),dict(inventory=True),dict(inventory=1.5),dict(price_minor=True),dict(kind='bad'),dict(kind='service'),dict(allow_multiple='yes'),dict(variants=[dict(id=str(uuid.uuid4()),label='M',inventory=3)])]:
   with self.subTest(kw=kw),self.assertRaises(ValueError):validate(dict(items=[item(**kw)]))
  self.assertIsNone(validate(dict(items=[item(inventory=None)]))['items'][0]['inventory'])
 def test_quote_inventory_quantities_variants_tax_and_totals(self):
  row=item();p=dict(items=[row]);selection=dict(item_id=row['id'],quantity=2)
  q=quote(p,[selection]);self.assertEqual(q['item_subtotal_minor'],5000);self.assertTrue(q['tax_pending']);self.assertFalse(q['reserved']);self.assertNotIn('tax_minor',q)
  for bad in [dict(quantity=6),dict(quantity=True),dict(quantity=1.5),dict(quantity=0),dict(item_id=str(uuid.uuid4()))]:
   with self.subTest(bad=bad),self.assertRaises(ValueError):quote(p,[selection|bad])
  with self.assertRaises(ValueError):quote(p,[selection,selection])
  row['inventory']=0
  with self.assertRaises(ValueError):quote(p,[selection])
  a,b=str(uuid.uuid4()),str(uuid.uuid4());row.update(inventory=None,allow_multiple=False,variants=[dict(id=a,label='Medium',inventory=2),dict(id=b,label='Large',inventory=0)])
  self.assertEqual(quote(p,[selection|dict(quantity=1,variant_id=a)])['item_subtotal_minor'],2500)
  for selections in [[selection],[selection|dict(quantity=1,variant_id=b)],[selection|dict(quantity=2,variant_id=a)],[selection|dict(quantity=1,variant_id=a),selection|dict(quantity=1,variant_id=b)]]:
   with self.assertRaises(ValueError):quote(p,selections)
class ExtrasStorage(unittest.TestCase):
 setUp=test_events.PostgresTest.setUp;tearDown=test_events.PostgresTest.tearDown;start=test_events.PostgresTest.start;stop=test_events.PostgresTest.stop;request=test_events.PostgresTest.request;auth_headers=test_events.PostgresTest.auth_headers
 def test_save_isolation_conflict_restart_quote_and_delete(self):
  first=self.request('/api/events',draft(),'POST');other=self.request('/api/events',draft(),'POST');path='/api/events/'+first['id']+'/extra-options';p=self.request(path);row=item();p['items']=[row];saved=self.request(path,p,'PUT')
  self.assertEqual(saved['revision'],1);self.assertEqual(self.request('/api/events/'+other['id']+'/extra-options')['items'],[])
  flows=self.request('/api/events/'+first['id']+'/flows',dict(name='Exhibitor',kind='exhibitor'),'POST');child=next(f['id'] for f in flows if f['name']=='Exhibitor');self.assertEqual(self.request('/api/events/'+child+'/extra-options')['items'],[])
  with self.assertRaises(HTTPError):self.request(path,p,'PUT')
  q=self.request(path+'/quote',dict(selections=[dict(item_id=row['id'],quantity=3)]),'POST');self.assertEqual(q['item_subtotal_minor'],7500);self.assertEqual(self.request(path),saved)
  self.stop();self.start();self.assertEqual(self.request(path),saved)
  self.request('/api/events/'+first['id'],dict(confirm_name=first['name']),'DELETE')
  with self.assertRaises(HTTPError):self.request(path)
