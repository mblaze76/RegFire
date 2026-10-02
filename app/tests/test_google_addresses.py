import unittest
from unittest.mock import patch
import google_addresses as g
class GoogleAddressTests(unittest.TestCase):
 def test_components_preserve_suite(self):
  row=g.normalize({'addressComponents':[{'types':['street_number'],'longText':'1600'},{'types':['route'],'longText':'Amphitheatre Parkway'},{'types':['locality'],'longText':'Mountain View'},{'types':['subpremise'],'longText':'Overwrite'}],'formattedAddress':'Public test address'})
  self.assertEqual(row['line1'],'1600 Amphitheatre Parkway');self.assertEqual(row['city'],'Mountain View');self.assertNotIn('line2',row)
 def test_invalid_identifiers_never_request(self):
  with patch.object(g,'request') as req:
   for value in ['../secrets','https://elsewhere.test/',None]:
    with self.assertRaises(ValueError):g.details(value,'session')
   with self.assertRaises(ValueError):g.suggest('Address','bad session')
   req.assert_not_called()
 def test_only_requested_address_fields(self):
  with patch.object(g,'request',return_value={'formattedAddress':'Example'}) as req:
   g.details('public-place','session')
   self.assertEqual(req.call_args.kwargs['mask'],'addressComponents,formattedAddress')
 def test_predictions_not_queries(self):
  with patch.object(g,'request',return_value={'suggestions':[{'placePrediction':{'placeId':'place123','text':{'text':'Public address'}}},{'queryPrediction':{'text':{'text':'query'}}}]}):
   rows=g.suggest('Public','session')['suggestions'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['place_id'],'place123')
if __name__=='__main__':unittest.main()
