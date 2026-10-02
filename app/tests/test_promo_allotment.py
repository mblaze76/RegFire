import unittest
from registration import starter,validate_page
class PromoAllotmentTests(unittest.TestCase):
 def test_allotment_validation(self):
  base=starter({'id':'example','name':'Example'})
  promo={'code':'SAVE','type':'percent','amount':10}
  for value in (None,0,1,100,2147483647):
   with self.subTest(value=value):
    result=validate_page(base|{'promo_codes':[promo|{'allotment':value}]})
    self.assertEqual(result['promo_codes'][0]['allotment'],value)
  for value in (-1,1.5,True,'10',2147483648):
   with self.subTest(value=value),self.assertRaisesRegex(ValueError,'allotment'):
    validate_page(base|{'promo_codes':[promo|{'allotment':value}]})
  self.assertIsNone(validate_page(base|{'promo_codes':[promo]})['promo_codes'][0]['allotment'])
