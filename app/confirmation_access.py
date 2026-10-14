"""Read-only individual receipts: existing attendee account or expiring email link."""
import base64,json,re,secrets
from pathlib import Path
from urllib.parse import urlsplit
from psycopg import sql
import psycopg
from attendee_accounts import identity,digest,table,respond,throttle
from access import AccessError
from deployment_config import DeploymentConfig
UUID=r'[a-f0-9-]{36}'
def email_link(c,store,order,origin):
 base=origin+'/attendee-confirmation#order='+order['id']
 if order.get('group_parent_id',order['id'])==order['id']:return base
 token=secrets.token_urlsafe(32)
 c.execute(sql.SQL("INSERT INTO {}(order_id,token_hash) VALUES(%s,%s) ON CONFLICT(order_id) DO UPDATE SET token_hash=excluded.token_hash,expires=now()+interval '7 days'").format(table(store,'confirmation_links')),(order['id'],digest(token)))
 return base+'&key='+token

def authorized(store,ident,who,key):
 if not isinstance(ident,str) or not re.fullmatch(UUID,ident):raise AccessError('Confirmation unavailable.',404)
 with store.connect() as c:
  if key:
   if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',key):raise AccessError('Confirmation link is invalid or expired.',403)
   grant=c.execute(sql.SQL('SELECT 1 FROM {} WHERE order_id=%s AND token_hash=%s AND expires>now()').format(table(store,'confirmation_links')),(ident,digest(key))).fetchone()
  else:
   if not who:raise AccessError('Sign in to your attendee account.',401)
   grant=c.execute(sql.SQL('SELECT 1 FROM {} WHERE order_id=%s AND account_id=%s').format(table(store,'attendee_order_access')),(ident,who['id'])).fetchone()
  if not grant:raise AccessError('Confirmation unavailable for this account or link.',403)
  row=c.execute(sql.SQL("SELECT body FROM {} WHERE id=%s AND status IN ('paid','confirmed_free')").format(table(store,'registration_orders')),(ident,)).fetchone()
 if not row or row[0].get('mode')=='sandbox':raise AccessError('Confirmation unavailable.',404)
 return row[0]

def handle(h):
 path=urlsplit(h.path).path
 if path not in ('/attendee-confirmation','/attendee-confirmation.js','/api/attendee/receipt'):return False
 from confirmation import send_bytes,document
 try:
  if path!='/api/attendee/receipt':
   if h.command!='GET':raise AccessError('Use GET.',405)
   name='attendee-confirmation.html' if path=='/attendee-confirmation' else 'attendee-confirmation.js'
   send_bytes(h,(Path(__file__).parent/'static'/name).read_bytes(),'text/html' if name.endswith('.html') else 'text/javascript');return True
  if h.command!='POST':raise AccessError('Use POST.',405)
  if not DeploymentConfig.load(h.server.server_port).allows_origin(h.headers.get('Origin'),h.headers.get('Host','')):raise AccessError('Use this confirmation page.',403)
  size=int(h.headers.get('Content-Length',0))
  if not 0<size<=1024:raise AccessError('Invalid request.',400)
  data=json.loads(h.rfile.read(size))
  if not isinstance(data,dict):raise AccessError('Invalid request.',400)
  throttle(('receipt',h.client_address[0]))
  store=h.server.store;o=authorized(store,data.get('order'),identity(h),data.get('key'))
  doc=document(store,o['flow_id'],o);doc['settings']['show_wallet']=False;root=Path(getattr(h.server,'upload_root',Path(__file__).parent/'uploads'))
  if data.get('format')=='pdf':
   from confirmation_pdf import render
   send_bytes(h,render(doc,store,root),'application/pdf','RegFire-confirmation.pdf');return True
  from confirmation_email import prepare
  view=prepare(doc,store,root);html=view['html']
  for image in view['inline_images']:html=html.replace('cid:'+image['content_id'],'data:image/png;base64,'+base64.b64encode(image['data']).decode())
  respond(h,200,{'html':html,'confirmation_id':o['id']})
 except AccessError as e:respond(h,e.status,{'error':str(e)})
 except (ValueError,TypeError,KeyError):respond(h,400,{'error':'Confirmation could not be read.'})
 except (OSError,psycopg.Error):respond(h,503,{'error':'Confirmation temporarily unavailable.'})
 return True
