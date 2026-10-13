"""Run the public attendee contract through the production WSGI adapter."""
import io,json,os
from unittest.mock import patch
from urllib.error import HTTPError
from test_public_attendee import PublicAttendeeTests
from deployment_config import DeploymentConfig
from production_wsgi import Application

class PublicWSGITests(PublicAttendeeTests):
 def public(self,path,data=None,method=None):
  from urllib.parse import urlsplit
  origin='https://staging.example.test';route=urlsplit(path)
  config=DeploymentConfig.load(self.server.server_port,dict(REGFIRE_ENV='production',REGFIRE_PUBLIC_ORIGIN=origin))
  app=Application(self.server,config);result={};body=b'' if data is None else json.dumps(data).encode()
  env={'REQUEST_METHOD':method or ('POST' if data is not None else 'GET'),'PATH_INFO':route.path,'QUERY_STRING':route.query,'HTTP_HOST':'staging.example.test','HTTP_ORIGIN':origin,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(body)),'HTTP_COOKIE':self.attendee_cookie,'HTTP_X_ATTENDEE_CSRF':self.attendee_csrf,'REMOTE_ADDR':'127.0.0.1','wsgi.input':io.BytesIO(body)}
  def start(status,headers):result.update(code=int(status[:3]),headers=dict(headers))
  with patch.dict(os.environ,REGFIRE_ENV='production',REGFIRE_PUBLIC_ORIGIN=origin):payload=b''.join(app(env,start))
  if result['headers'].get('Set-Cookie'):
   self.assertIn('; Secure;',result['headers']['Set-Cookie']);self.attendee_cookie=result['headers']['Set-Cookie'].split(';')[0]
  if result['code']>=400:raise HTTPError(path,result['code'],'Request denied',{},io.BytesIO(payload))
  return json.loads(payload)
