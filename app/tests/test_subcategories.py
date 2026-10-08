import unittest
from registration import starter,validate_page
class SubcategoryTests(unittest.TestCase):
 def page(self):return starter({'id':'test','name':'Test'})
 def test_nested_roundtrip_preserves_parent_price(self):
  p=self.page();p['regtypes'][0].update(price_minor=29500,subcategories=[{'id':'day','name':'Day','subcategories':[{'id':'tue','name':'Tuesday'},{'id':'wed','name':'Wednesday'}]}]);saved=validate_page(p)
  self.assertEqual(saved['regtypes'][0]['price_minor'],29500)
  self.assertEqual(saved['regtypes'][0]['subcategories'][0]['subcategories'][1]['name'],'Wednesday')
  self.assertEqual(validate_page(saved),saved)
 def test_rejects_duplicate_siblings_and_ids(self):
  for choices in [[{'id':'a','name':'Day'},{'id':'b','name':'day'}],[{'id':'a','name':'One'},{'id':'a','name':'Two'}],[{'id':'a','name':''}]]:
   p=self.page();p['regtypes'][0]['subcategories']=choices
   with self.assertRaises(ValueError):validate_page(p)
 def test_depth_limit(self):
  p=self.page();branch=p['regtypes'][0]
  for i in range(6):branch['subcategories']=[{'id':str(i),'name':'Nested'}];branch=branch['subcategories'][0]
  with self.assertRaises(ValueError):validate_page(p)
 def test_legacy_defaults_empty(self):self.assertEqual(validate_page(self.page())['regtypes'][0]['subcategories'],[])
