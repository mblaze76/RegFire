import unittest,sys,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from address_lookup import config,suggestions,normalize
from membership import Unavailable

class AddressTests(unittest.TestCase):
    def test_unconfigured_never_contacts_provider(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(config()['configured'])
            result=suggestions('123 Main',lambda *args:self.fail('Provider must not be called'))
            self.assertEqual(result['status'],'unconfigured')
    def test_response_components_do_not_replace_suite(self):
        data={'results':[dict(address_line1='10 Main Street',address_line2='Provider city line',city='Example',state='New York',postcode='10001',country='United States',formatted='10 Main Street, Example')]}
        result=normalize(data)[0]
        self.assertEqual(result['line1'],'10 Main Street');self.assertNotIn('line2',result);self.assertEqual(result['postal'],'10001')
        self.assertEqual(normalize({'results':[{'street':'Main','housenumber':'10','village':'Example'}]})[0]['city'],'Example')
    def test_fixture_and_validation(self):
        with patch.dict(os.environ,{'REGFIRE_ADDRESS_PROVIDER':'fixture'},clear=True):
            result=suggestions('123 Example');self.assertEqual(result['status'],'fixture');self.assertEqual(result['suggestions'][0]['line1'],'123 Example Street')
            self.assertEqual(suggestions('Unknown')['suggestions'],[])
        for query in ['', 'ab', 'a'*301, None,'abc\n']:
            with self.assertRaises(ValueError):suggestions(query)
    def test_configured_response_and_failure_fallback(self):
        with patch.dict(os.environ,{'REGFIRE_ADDRESS_PROVIDER':'geoapify','REGFIRE_GEOAPIFY_API_KEY':'synthetic-test-only'},clear=True),patch('address_lookup._last_call',0):
            result=suggestions('123 Main',lambda q,key:{'results':[{'address_line1':'123 Main','formatted':'123 Main'}]})
            self.assertEqual(result['status'],'ready');self.assertNotIn('synthetic-test-only',str(config()))
        with patch.dict(os.environ,{'REGFIRE_ADDRESS_PROVIDER':'geoapify','REGFIRE_GEOAPIFY_API_KEY':'synthetic-test-only'},clear=True),patch('address_lookup._last_call',0):
            def failure(*args):raise Unavailable('Do not reveal secrets')
            result=suggestions('123 Main',failure);self.assertEqual(result['status'],'unavailable');self.assertNotIn('secrets',str(result))
