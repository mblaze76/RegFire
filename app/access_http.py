"""HTTP boundary: every non-public route requires identity and a current product grant."""
import json,hmac,re,threading
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
import psycopg
from access import Access,AccessError
PUBLIC={'/api/linkedin/callback','/api/auth/forgot-password','/api/auth/reset-password','/api/registrant-event','/registrant-login','/registrant-login.js','/login','/access.css','/access-ui.js','/regfire-logo.png','/api/auth/me','/api/auth/login','/api/auth/activate','/api/auth/setup'}
STATIC={'/welcome-heading.js','/flows.js','/welcome-site.js','/welcome.js','/style.css','/app.js','/builder.js','/demographics.js','/membership.js','/address.js','/footer.js','/email.js','/autosave.js','/live-editor.js','/live-preview.js','/auth-client.js'}
def cookie_name(h):return 'regfire_session_'+str(h.server.server_port)
def raw_cookie(h):
 try:
  c=SimpleCookie();c.load(h.headers.get('Cookie',''));return c[cookie_name(h)].value if cookie_name(h) in c else ''
 except Exception:return ''
def access(h):
 if not hasattr(h.server,'access'):h.server.access=Access(h.server.store)
 return h.server.access
_recovery_lock=threading.Lock()
def recovery(h):
 from password_recovery import PasswordRecovery
 with _recovery_lock:
  if not hasattr(h.server,'recovery'):
   from communications import settings_for
   from communications_providers import RecoveryTransport
   h.server.recovery=PasswordRecovery(access(h),RecoveryTransport(settings_for(h.server)))
 return h.server.recovery
def guard(h):
 path=urlsplit(h.path).path
 try:
  a=access(h);h.identity=a.session(raw_cookie(h))
  if h.command not in ('GET','HEAD'):
   if h.headers.get('Origin')!='http://'+h.headers.get('Host',''):raise AccessError('Use this app to submit changes.',403)
  if path in PUBLIC or (h.command=='GET' and path in STATIC):return True
  if not h.identity:
   if h.command=='GET' and not path.startswith('/api/'):
    h.send_response(303);h.send_header('Location','/login');h.send_header('Cache-Control','no-store');h.end_headers();return False
   raise AccessError('Sign in to continue.',401)
  if h.command not in ('GET','HEAD') and not hmac.compare_digest(h.headers.get('X-CSRF-Token',''),h.identity['csrf']):raise AccessError('Refresh the page before submitting changes.',403)
  if path in ('/communications','/communications.js','/communications.css','/api/admin/communications'):
   from communications import require_owner
   require_owner(a,h.identity)
  elif path.startswith('/api/admin/') or path=='/admin':a.require_admin(h.identity)
  elif path not in ('/products','/api/auth/logout') and 'event-builder' not in h.identity['products']:raise AccessError('RegFire Nexus access is required.',403)
  event_match=re.match(r'^/api/events/([^/]+)(?:/|$)',path)
  if event_match:a.require_event(h.identity,event_match[1])
  return True
 except AccessError as e:h.respond(e.status,{'error':str(e)});return False
 except psycopg.Error:h.respond(503,{'error':'Sign-in storage is unavailable.'});return False

def respond(h,status,data,cookie=None):
 content=json.dumps(data).encode();h.send_response(status);h.send_header('Content-Type','application/json');h.send_header('Cache-Control','no-store');h.send_header('Content-Length',str(len(content)))
 if cookie is not None:h.send_header('Set-Cookie',cookie_name(h)+'='+cookie+'; HttpOnly; SameSite=Strict; Path=/; Max-Age='+('28800' if cookie else '0'))
 h.end_headers();h.wfile.write(content)
def handle(h):
 path=urlsplit(h.path).path
 if not path.startswith(('/api/auth/','/api/admin/')):return False
 try:
  a=access(h);data={}
  if h.command=='POST':
   if not h.headers.get('Content-Type','').startswith('application/json'):raise AccessError('Send JSON.')
   size=int(h.headers.get('Content-Length','0'))
   if not 0<size<=16384:raise AccessError('Request is missing or too large.')
   data=json.loads(h.rfile.read(size))
   if not isinstance(data,dict):raise AccessError('Send an object.')
  if path=='/api/auth/me' and h.command=='GET':respond(h,200,{'user':h.identity,'recovery_available':recovery(h).mailer.configured,'setup_required':not a.configured(),'owner_email':__import__('owner_setup').owner_email() if not a.configured() else None,'products':a.products() if h.identity else []})
  elif path=='/api/auth/setup' and h.command=='POST':
   import owner_setup
   a.throttle();owner_setup.finish(a,data.get('token'),data.get('password'));respond(h,200,{'ok':True})
  elif path=='/api/auth/login' and h.command=='POST':respond(h,200,{'ok':True},a.login(data.get('email'),data.get('password')))
  elif path=='/api/auth/activate' and h.command=='POST':a.activate(data.get('email'),data.get('token'),data.get('password'));respond(h,200,{'ok':True})
  elif path=='/api/auth/forgot-password' and h.command=='POST':respond(h,200,{'message':recovery(h).request(data.get('email'),h.client_address[0])})
  elif path=='/api/auth/reset-password' and h.command=='POST':recovery(h).complete(data.get('token'),data.get('password'),h.client_address[0]);respond(h,200,{'ok':True},'')
  elif path=='/api/auth/logout' and h.command=='POST':a.logout(raw_cookie(h));respond(h,200,{'ok':True},'')
  elif path=='/api/admin/users' and h.command=='GET':respond(h,200,{'recovery':recovery(h).status(),'users':a.users(h.identity),'products':a.products(),'events':[dict(id=e['id'],name=e['name']) for e in a.event_list(h.identity)]})
  elif path=='/api/admin/users' and h.command=='POST':respond(h,200,{'id':a.save_user(h.identity,data)})
  elif path=='/api/admin/products' and h.command=='POST':a.save_product(h.identity,data);respond(h,200,{'ok':True})
  elif path=='/api/admin/enrollment' and h.command=='POST':respond(h,200,{'token':a.enrollment(h.identity,data.get('user_id')),'expires_in_hours':24})
  elif path=='/api/admin/audit' and h.command=='GET':respond(h,200,{'entries':a.audit_rows(h.identity)})
  else:respond(h,404,{'error':'Not found.'})
 except (ValueError,UnicodeDecodeError):respond(h,400,{'error':'Invalid request.'})
 except AccessError as e:respond(h,e.status,{'error':str(e)})
 except psycopg.Error:respond(h,503,{'error':'Access settings could not be updated. Please retry.'})
 return True
