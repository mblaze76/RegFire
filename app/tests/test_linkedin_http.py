import unittest
import uuid
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch
import tests.test_events as events


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class LinkedInHTTPTests(unittest.TestCase):
    setUp = events.PostgresTest.setUp
    tearDown = events.PostgresTest.tearDown
    start = events.PostgresTest.start
    stop = events.PostgresTest.stop
    request = events.PostgresTest.request
    auth_headers = events.PostgresTest.auth_headers

    def test_unconfigured_and_public_callback_do_not_expose_credentials(self):
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(self.request('/api/linkedin/status'), {'available': False})
        with build_opener(ProxyHandler({})).open(self.url + '/api/linkedin/callback?state=invalid') as response:
            body = response.read().decode()
            self.assertIn('could not be completed', body)
            self.assertNotIn('postMessage(', body)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_callback_requires_browser_cookie_and_returns_profile_once(self):
        event = self.request('/api/events', events.draft(), 'POST')
        request_id = str(uuid.uuid4())
        env = {'REGFIRE_LINKEDIN_CLIENT_ID': 'synthetic-client', 'REGFIRE_LINKEDIN_CLIENT_SECRET': 'synthetic-secret',
               'REGFIRE_LINKEDIN_REDIRECT_URI': self.url + '/api/linkedin/callback'}
        with patch.dict('os.environ', env):
            opener = build_opener(ProxyHandler({}), NoRedirect())
            with self.assertRaises(HTTPError) as redirect:
                opener.open(Request(self.url + '/api/linkedin/start?flow=' + event['id'] + '&request=' + request_id, headers=self.auth_headers()))
            self.assertEqual(redirect.exception.code, 303)
            headers = redirect.exception.headers
            query = parse_qs(urlsplit(headers['Location']).query)
            self.assertEqual(query['scope'], ['openid profile email'])
            self.assertNotIn('synthetic-secret', headers['Location'])
            cookie = headers['Set-Cookie'].split(';')[0]
            callback = self.url + '/api/linkedin/callback?code=synthetic-code&state=' + query['state'][0]
            with patch('linkedin_import.profile_from_code', return_value={'given_name': 'Example', 'email': 'example@example.test'}) as provider:
                with opener.open(callback) as response:
                    self.assertNotIn('postMessage(', response.read().decode())
                provider.assert_not_called()
                with opener.open(Request(callback, headers={'Cookie': cookie})) as response:
                    body = response.read().decode()
                    self.assertIn('example@example.test', body)
                    self.assertIn(request_id, body)
                    self.assertNotIn('synthetic-secret', body)
                    self.assertNotIn('synthetic-code', body)
                provider.assert_called_once()
                with opener.open(Request(callback, headers={'Cookie': cookie})) as response:
                    self.assertNotIn('example@example.test', response.read().decode())
                provider.assert_called_once()


if __name__ == '__main__':
    unittest.main()
