import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from linkedin_import import Transactions, configuration, profile_from_code, validate_token


class LinkedInImportTests(unittest.TestCase):
    def test_configuration_requires_exact_local_callback_and_secret(self):
        origin = 'http://127.0.0.1:8766'
        env = {'REGFIRE_LINKEDIN_CLIENT_ID': 'test-client', 'REGFIRE_LINKEDIN_CLIENT_SECRET': 'synthetic-secret',
               'REGFIRE_LINKEDIN_REDIRECT_URI': origin + '/api/linkedin/callback'}
        with patch.dict('os.environ', env, clear=True):
            self.assertIsNotNone(configuration(origin))
            self.assertIsNone(configuration('http://localhost:8766'))
        with patch.dict('os.environ', {}, clear=True):
            self.assertIsNone(configuration(origin))

    def test_browser_bound_expiring_single_use_state(self):
        clock = [0]
        store = Transactions(lambda: clock[0])
        state, binding, nonce = store.start('flow', 'request', 'http://localhost', 'client')
        with self.assertRaises(ValueError):
            store.consume(state, 'wrong-browser')
        self.assertEqual(store.consume(state, binding)['nonce'], nonce)
        with self.assertRaises(ValueError):
            store.consume(state, binding)
        state, binding, _ = store.start('flow', 'request', 'http://localhost', 'client')
        clock[0] = 601
        with self.assertRaises(ValueError):
            store.consume(state, binding)

    def test_signed_id_token_validation(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        claims = dict(iss='https://www.linkedin.com', sub='synthetic-member', aud='client',
                      iat=int(time.time()), exp=int(time.time()) + 300, nonce='nonce')
        with patch('jwt.PyJWKClient') as client:
            client.return_value.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
            encode = lambda values: jwt.encode(values, key, algorithm='RS256')
            self.assertEqual(validate_token(encode(claims), 'client', 'nonce')['sub'], 'synthetic-member')
            for changes in ({'aud': 'other'}, {'iss': 'https://other.example'}, {'nonce': 'other'},
                            {'exp': int(time.time()) - 1}, {'azp': 'other'}):
                with self.subTest(changes=changes), self.assertRaises((ValueError, jwt.PyJWTError)):
                    validate_token(encode({**claims, **changes}), 'client', 'nonce')

    def test_only_permitted_profile_fields_and_optional_email(self):
        config = dict(CLIENT_ID='client', CLIENT_SECRET='synthetic-secret', REDIRECT_URI='http://localhost/api/linkedin/callback')
        profile = dict(sub='member', given_name='Sample', family_name='Attendee', company='Do not import', picture='https://example.test/photo')
        with patch('linkedin_import.validate_token', return_value={'sub': 'member'}), patch('linkedin_import.fetch_json', side_effect=[{'access_token': 'synthetic', 'id_token': 'synthetic'}, profile]) as request:
            self.assertEqual(profile_from_code('code', {'nonce': 'nonce'}, config), {'given_name': 'Sample', 'family_name': 'Attendee'})
            self.assertEqual(request.call_args.kwargs['token'], 'synthetic')
        with patch('linkedin_import.validate_token', return_value={'sub': 'different'}), patch('linkedin_import.fetch_json', side_effect=[{'access_token': 'synthetic', 'id_token': 'synthetic'}, profile]):
            with self.assertRaises(ValueError):
                profile_from_code('code', {'nonce': 'nonce'}, config)


if __name__ == '__main__':
    unittest.main()
