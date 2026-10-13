import unittest
from deployment_config import DeploymentConfig

class DeploymentBoundaryTests(unittest.TestCase):
    def test_local_defaults_preserve_loopback_only(self):
        c=DeploymentConfig.load(8765,{})
        self.assertTrue(c.allows_origin('http://localhost:8765','localhost:8765'))
        self.assertFalse(c.allows_host('evil.example'))
        self.assertFalse(c.secure_cookies)
    def test_production_is_explicit_and_https_only(self):
        for origin in ['', 'http://reg.example', 'https://reg.example/path', 'https://user@reg.example', 'https://reg.example?x=1', 'https://reg.example:bad']:
            with self.assertRaises(ValueError):DeploymentConfig.load(8765,{'REGFIRE_ENV':'production','REGFIRE_PUBLIC_ORIGIN':origin})
    def test_production_rejects_cross_origin_and_localhost(self):
        c=DeploymentConfig.load(8765,{'REGFIRE_ENV':'production','REGFIRE_PUBLIC_ORIGIN':'https://reg.example'})
        self.assertTrue(c.secure_cookies)
        self.assertTrue(c.allows_origin('https://reg.example','reg.example'))
        self.assertFalse(c.allows_origin('http://reg.example','reg.example'))
        self.assertFalse(c.allows_origin('https://evil.example','reg.example'))
        self.assertFalse(c.allows_host('localhost:8765'))
