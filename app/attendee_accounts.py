from deployment_config import DeploymentConfig
"""Attendee identities are isolated from organizer grants and registration answer JSON."""
import hashlib,hmac,json,re,secrets,threading,time,uuid
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from psycopg import sql
import psycopg
from access import AccessError,email,password_hash,password_ok

PUBLIC={'/api/attendee/edit','/api/attendee/login','/api/attendee/me','/api/attendee/logout','/api/attendee/registrations'}
_lock=threading.Lock();_attempts={}
def table(s,n):return sql.Identifier(s.schema,n)
def digest(v):return hashlib.sha256(v.encode()).hexdigest()
def throttle(key):
 with _lock:
  now=time.monotonic()
  for k in list(_attempts):
   _attempts[k]=[t for t in _attempts[k] if t>now-900]
   if not _attempts[k]:del _attempts[k]
  hits=_attempts.setdefault(key,[])
  if len(hits)>=12:raise AccessError('Too many attempts. Try again in 15 minutes.',429)
  hits.append(now)
def cookie(h):return 'regfire_attendee_'+str(h.server.server_port)
def raw_cookie(h):
 try:
  c=SimpleCookie();c.load(h.headers.get('Cookie',''));return c[cookie(h)].value if cookie(h) in c else ''
 except Exception:return ''
def respond(h,status,data,token=None):
 b=json.dumps(data).encode();h.send_response(status);h.send_header('Content-Type','application/json');h.send_header('Cache-Control','no-store');h.send_header('Content-Length',str(len(b)))
 if token is not None:h.send_header('Set-Cookie',cookie(h)+'='+token+('; Secure' if DeploymentConfig.load(h.server.server_port).secure_cookies else '')+'; HttpOnly; SameSite=Strict; Path=/; Max-Age='+('28800' if token else '0'))
 h.end_headers();h.wfile.write(b)
def identity(h):
 with h.server.store.connect() as c:
  r=c.execute(sql.SQL('SELECT s.account_id,s.csrf,a.email FROM {} s JOIN {} a ON a.id=s.account_id WHERE s.token_hash=%s AND s.expires>now()').format(table(h.server.store,'attendee_sessions'),table(h.server.store,'attendee_accounts')),(digest(raw_cookie(h)),)).fetchone()
 return dict(id=str(r[0]),csrf=r[1],email=r[2]) if r else None

def prepare(store,actor,flow,data):
 if data.get('preview') is not False:raise ValueError('Account setup is unavailable in a preview.')
 address=email(data.get('email'));password=data.get('password');confirm=data.get('confirm_password')
 if not isinstance(password,str) or not isinstance(confirm,str) or not hmac.compare_digest(password.encode(),confirm.encode()):raise ValueError('Passwords do not match.')
 encoded=password_hash(password);token=secrets.token_urlsafe(32)
 with store.connect() as c:
  r=c.execute(sql.SQL('SELECT id,password_hash FROM {} WHERE email=%s').format(table(store,'attendee_accounts')),(address,)).fetchone()
  if r and not password_ok(password,r[1]):raise ValueError('An account already uses this email. Enter its existing password; a new registration cannot replace it.')
  c.execute(sql.SQL('DELETE FROM {} WHERE expires<now() AND order_id IS NULL').format(table(store,'attendee_enrollments')))
  c.execute(sql.SQL('INSERT INTO {}(token_hash,actor_id,flow_id,email,password_hash,account_id) VALUES(%s,%s,%s,%s,%s,%s)').format(table(store,'attendee_enrollments')),(digest(token),actor,flow,address,encoded,r[0] if r else None))
 return token

def bind(c,store,order,token):
 if not token:return
 if not isinstance(token,str) or len(token)>200:raise ValueError('Re-enter your attendee password on the details page.')
 r=c.execute(sql.SQL('SELECT email,order_id FROM {} WHERE token_hash=%s AND actor_id=%s AND flow_id=%s AND expires>now() FOR UPDATE').format(table(store,'attendee_enrollments')),(digest(token),order['actor_id'],order['flow_id'])).fetchone()
 if not r:raise ValueError('Re-enter your attendee password on the details page.')
 if r[1] and str(r[1])!=order['id']:
  previous=c.execute(sql.SQL('SELECT body,status FROM {} WHERE id=%s FOR UPDATE').format(table(store,'registration_orders')),(r[1],)).fetchone()
  if not previous or previous[1]!='pending' or previous[0]['actor_id']!=order['actor_id'] or previous[0]['flow_id']!=order['flow_id']:raise ValueError('Re-enter your attendee password on the details page.')

 from registration import starter
 page=c.execute(sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(table(store,'registration_pages')),(order['flow_id'],)).fetchone()
 fields=page[0]['fields'] if page else starter({'id':order['flow_id'],'name':''})['fields']
 addresses=[v for f in fields if f['type']=='email' for v in [order['data']['contacts'].get(f['id'],'').strip().lower()] if v]
 if r[0] not in addresses:raise ValueError('The account email must match your attendee email. Return to details.')
 c.execute(sql.SQL('UPDATE {} SET order_id=%s,expires=now()+interval \'2 days\' WHERE token_hash=%s').format(table(store,'attendee_enrollments')),(order['id'],digest(token)))

def complete(c,store,order):
 if order['status'] not in ('paid','confirmed_free') or order.get('mode')=='sandbox':return
 r=c.execute(sql.SQL('SELECT email,password_hash,account_id FROM {} WHERE order_id=%s FOR UPDATE').format(table(store,'attendee_enrollments')),(order['id'],)).fetchone()
 if not r:return
 account=r[2]
 if not account:
  account=uuid.uuid4()
  created=c.execute(sql.SQL('INSERT INTO {}(id,email,password_hash) VALUES(%s,%s,%s) ON CONFLICT(email) DO NOTHING RETURNING id').format(table(store,'attendee_accounts')),(account,r[0],r[1])).fetchone()
  if not created:return # Never attach to an email claimed after preparation without verifying that account.
 c.execute(sql.SQL('INSERT INTO {}(order_id,account_id) VALUES(%s,%s) ON CONFLICT DO NOTHING').format(table(store,'attendee_order_access')),(order['id'],account))
 c.execute(sql.SQL('DELETE FROM {} WHERE order_id=%s').format(table(store,'attendee_enrollments')),(order['id'],))

def handle(h):
 path=urlsplit(h.path).path;m=re.fullmatch(r'/api/events/([a-f0-9-]{36})/attendee-account',path)
 if path not in PUBLIC and not m:return False
 try:
  store=h.server.store;data={}
  if h.command=='POST':
   size=int(h.headers.get('Content-Length',0))
   if not 0<size<=4096:raise ValueError('Invalid account request.')
   data=json.loads(h.rfile.read(size))
   if not isinstance(data,dict):raise ValueError('Invalid account request.')
  if m:
   if h.command!='POST':raise ValueError('Use POST.')
   throttle(('prepare',h.identity['id']));token=prepare(store,h.identity['id'],m[1],data)
   respond(h,200,{'enrollment_token':token,'message':'Password prepared securely. Account access starts after completed registration.'});return True
  if path=='/api/attendee/login' and h.command=='POST':
   throttle(('login',h.client_address[0]));address=email(data.get('email'));password=data.get('password')
   with store.connect() as c:
    r=c.execute(sql.SQL('SELECT id,password_hash FROM {} WHERE email=%s').format(table(store,'attendee_accounts')),(address,)).fetchone()
    # Perform a hash on unknown accounts too; account existence is not disclosed.
    valid=password_ok(password,r[1] if r else password_hash('dummy-attendee-password'))
    if not r or not valid:raise AccessError('Email or password is incorrect.',401)
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
    c.execute(sql.SQL('DELETE FROM {} WHERE expires<now()').format(table(store,'attendee_sessions')))
    c.execute(sql.SQL('INSERT INTO {}(token_hash,account_id,csrf) VALUES(%s,%s,%s)').format(table(store,'attendee_sessions')),(digest(token),r[0],csrf))
   respond(h,200,{'ok':True},token);return True
  who=identity(h)
  if path=='/api/attendee/me' and h.command=='GET':respond(h,200,{'user':who});return True
  if not who:raise AccessError('Sign in to your attendee account.',401)
  if h.command=='POST' and not hmac.compare_digest(h.headers.get('X-Attendee-CSRF',''),who['csrf']):raise AccessError('Refresh before submitting.',403)
  if path=='/api/attendee/logout' and h.command=='POST':
   with store.connect() as c:c.execute(sql.SQL('DELETE FROM {} WHERE token_hash=%s').format(table(store,'attendee_sessions')),(digest(raw_cookie(h)),))
   respond(h,200,{'ok':True},'');return True
  if path=='/api/attendee/edit':
   from attendee_edit import operation
   ident=data.get('id') if h.command=='POST' else parse_qs(urlsplit(h.path).query).get('id',[''])[0]
   if not re.fullmatch(r'[a-f0-9-]{36}',ident or ''):raise ValueError('Invalid registration.')
   respond(h,200,operation(store,who['id'],ident,data if h.command=='POST' else None));return True
  if path=='/api/attendee/registrations' and h.command=='GET':
   event=parse_qs(urlsplit(h.path).query).get('event',[''])[0]
   with store.connect() as c:
    rows=c.execute(sql.SQL("SELECT o.body FROM {} o JOIN {} a ON a.order_id=o.id WHERE a.account_id=%s AND o.status IN ('paid','confirmed_free') ORDER BY o.updated DESC").format(table(store,'registration_orders'),table(store,'attendee_order_access')),(who['id'],)).fetchall()
   result=[]
   for (o,) in rows:
    if event and o['parent_event_id']!=event and o['flow_id']!=event:continue
    result.append({k:o[k] for k in ('id','flow_id','parent_event_id','status','quote')})
   respond(h,200,{'registrations':result});return True
  raise ValueError('Unsupported account operation.')
 except AccessError as e:respond(h,e.status,{'error':str(e)})
 except (ValueError,TypeError,KeyError) as e:respond(h,400,{'error':str(e) if path=='/api/attendee/edit' else 'Check the email, password match and minimum 12-character password. Existing accounts require their current password.'})
 except psycopg.Error:respond(h,503,{'error':'Attendee account storage is unavailable. Please retry.'})
 return True
