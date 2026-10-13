import io,json,os,unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from production_wsgi import Application
from deployment_config import DeploymentConfig

class WSGIBoundaryTests(unittest.TestCase):
 def setUp(self):
  self.config=DeploymentConfig.load(8080,dict(REGFIRE_ENV='production',REGFIRE_PUBLIC_ORIGIN='https://staging.example.test'))
  self.app=Application(SimpleNamespace(server_port=8080,store=Mock(),access=Mock()),self.config)
 def request(self,path='/',method='GET',host='staging.example.test',body=b'',**extra):
  state={};env=dict(PATH_INFO=path,REQUEST_METHOD=method,HTTP_HOST=host,CONTENT_LENGTH=str(len(body)),**{'wsgi.input':io.BytesIO(body)},**extra)
  def start(status,headers):state.update(status=int(status[:3]),headers=dict(headers))
  state['body']=b''.join(self.app(env,start));return state
 def test_health_without_details(self):
  r=self.request('/health/live',host='10.0.0.1:8080');self.assertEqual(r['status'],200);self.assertEqual(json.loads(r['body']),{'status':'up'})
 def test_forwarded_host_does_not_override_host(self):
  self.assertEqual(self.request(host='evil.test',HTTP_X_FORWARDED_HOST='staging.example.test')['status'],403)
 def test_invalid_body_and_methods_never_reach_guard(self):
  with patch('access_http.guard') as guard:
   for kwargs,status in [({'method':'PATCH'},405),({'HTTP_TRANSFER_ENCODING':'chunked'},400)]:self.assertEqual(self.request(**kwargs)['status'],status)
   guard.assert_not_called()
 def test_no_exception_or_secret_in_response(self):
  with patch('access_http.guard',side_effect=ValueError('super-secret')):
   r=self.request();self.assertEqual(r['status'],503);self.assertNotIn(b'super-secret',r['body'])
 def test_https_cookie_and_organizer_guard_preserved(self):
  import access_http
  with patch.dict(os.environ,REGFIRE_ENV='production',REGFIRE_PUBLIC_ORIGIN=self.config.origin):
   self.app.server.access.session.return_value=None
   r=self.request('/api/events');self.assertEqual(r['status'],401)
   r=self.request('/api/auth/login','POST',body=b'{}',HTTP_ORIGIN='https://evil.test')
   self.assertEqual(r['status'],403)
   self.app.server.access.login.return_value='synthetic-token'
   r=self.request('/api/auth/login','POST',body=b'{}',HTTP_ORIGIN=self.config.origin,CONTENT_TYPE='application/json')
   self.assertEqual(r['status'],200);self.assertIn('; Secure;',r['headers']['Set-Cookie'])
