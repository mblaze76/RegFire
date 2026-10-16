"""WSGI bridge for existing handlers; sockets and HTTP parsing belong to Gunicorn.

No forwarded header is trusted. The ingress must preserve the canonical Host.
Organizer route guards remain intact; this does not publish draft event APIs.
"""
import io, json, logging, os, tempfile, threading
from email.message import Message
from http import HTTPStatus
from types import SimpleNamespace
from urllib.parse import quote
from server import Handler
from deployment_config import DeploymentConfig

log=logging.getLogger('regfire.requests')
log.setLevel(logging.INFO)
if not log.handlers:
    handler=logging.StreamHandler();handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'));log.addHandler(handler)
log.propagate=False
MAX_BODY=16*1024*1024

class Request(Handler):
    def __init__(self, environ, server):
        self.server=server
        self.command=environ['REQUEST_METHOD']
        self.path=quote(environ.get('PATH_INFO','/'),safe='/@:+')
        if environ.get('QUERY_STRING'):self.path+='?'+environ['QUERY_STRING']
        self.request_version='HTTP/1.1'
        self.requestline=self.command+' [redacted] HTTP/1.1'
        self.client_address=(environ.get('REMOTE_ADDR',''),0)
        self.headers=Message()
        for key,value in environ.items():
            if key.startswith('HTTP_'):self.headers[key[5:].replace('_','-')]=value
        for key in ('CONTENT_TYPE','CONTENT_LENGTH'):
            if environ.get(key):self.headers[key.replace('_','-')]=environ[key]
        self.rfile=environ['wsgi.input']
        self.wfile=tempfile.SpooledTemporaryFile(max_size=1024*1024)
        self.status=500;self.response_headers=[]
    def send_response(self, code, message=None):self.status=code
    def send_header(self, key, value):
        if '\r' in str(value) or '\n' in str(value):raise ValueError('Invalid response header')
        if key.lower() not in ('connection','transfer-encoding'):self.response_headers.append((key,str(value)))
    def end_headers(self):pass
    def log_message(self,*args):pass

class Application:
    def __init__(self, server, config):self.server,self.config=server,config
    def __call__(self,environ,start_response):
        request=Request(environ,self.server)
        try:
            path=environ.get('PATH_INFO','/')
            # Health probes return no private details and cannot reach handlers.
            if path=='/health/live' and request.command=='GET':request.respond(200,{'status':'up'})
            elif not self.config.allows_host(request.headers.get('Host')):request.respond(403,{'error':'Invalid host.'})
            elif path=='/health/ready' and request.command=='GET':
                with self.server.store.connect() as c:c.execute('SELECT 1')
                request.respond(200,{'status':'ready'})
            elif request.headers.get('Transfer-Encoding'):request.respond(400,{'error':'Unsupported request framing.'})
            else:
                length=request.headers.get('Content-Length','0')
                if not length.isdecimal():request.respond(400,{'error':'Invalid request length.'})
                elif int(length)>MAX_BODY:request.respond(413,{'error':'Request too large.'})
                elif request.command not in ('GET','POST','PUT','DELETE'):request.respond(405,{'error':'Method not allowed.'})
                else:
                    from access_http import guard
                    if guard(request):getattr(request,'do_'+request.command)( )
        except Exception:
            request.wfile.seek(0);request.wfile.truncate();request.response_headers=[]
            request.respond(503,{'error':'Service temporarily unavailable.'})
            # Never log exception text, URL, body, cookies, or tokens.
            log.error('request_failed')
        request.response_headers.extend([('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer')])
        if self.config.secure_cookies:request.response_headers.append(('Strict-Transport-Security','max-age=31536000'))
        start_response(str(request.status)+' '+HTTPStatus(request.status).phrase,request.response_headers)
        log.info('response status=%d method=%s',request.status,request.command if request.command in ('GET','POST','PUT','DELETE') else 'OTHER')
        request.wfile.seek(0)
        def body():
            try:
                while chunk:=request.wfile.read(65536):yield chunk
            finally:request.wfile.close()
        return body()

_application=None
_lock=threading.Lock()
def application(environ,start_response):
    global _application
    if _application is None:
        with _lock:
            if _application is None:
                from database import Store
                from access import Access
                from runtime_startup import prepare_store,prepare_owner
                config=DeploymentConfig.load(8080)
                if not config.secure_cookies:raise RuntimeError('WSGI runtime requires explicit production configuration.')
                store=Store();prepare_store(store,config);access=Access(store);prepare_owner(access,config)
                server=SimpleNamespace(server_port=8080,store=store,access=access)
                from confirmation_worker import start as start_confirmation_worker
                server.confirmation_stop=start_confirmation_worker(server)
                from partial_cleanup import start as start_partial_cleanup
                server.partial_stop=start_partial_cleanup(store)
                _application=Application(server,config)
    return _application(environ,start_response)
