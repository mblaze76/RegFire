"""Owner-only configuration boundary. No endpoint in this module sends messages."""
import json, threading
from urllib.parse import urlsplit
import psycopg
from access import AccessError
from communications_settings import Settings

_lock=threading.Lock()
def settings_for(server):
 with _lock:
  if not hasattr(server,'communications_settings'):
   server.communications_settings=Settings(getattr(server,'communications_settings_path',None))
  return server.communications_settings

def require_owner(access,actor):
 if not actor or actor.get('role')!='owner':raise AccessError('Super administrator access is required.',403)
 with access.store.connect() as c:
  row=c.execute(access.q("SELECT role,status FROM {} WHERE id=%s",'users'),(actor['id'],)).fetchone()
  if not row or row!=('owner','active'):raise AccessError('Super administrator access is required.',403)

def handle(h):
 if urlsplit(h.path).path!='/api/admin/communications':return False
 try:
  from access_http import access
  a=access(h);require_owner(a,h.identity);settings=settings_for(h.server)
  if h.command=='GET':return h.respond(200,settings.public()) or True
  if h.command!='POST':return h.respond(405,{'error':'Use GET or POST.'}) or True
  if not h.headers.get('Content-Type','').startswith('application/json'):raise AccessError('Send JSON.')
  length=int(h.headers.get('Content-Length','0'))
  if not 0<length<=8192:raise AccessError('Settings request is missing or too large.')
  data=json.loads(h.rfile.read(length))
  if not isinstance(data,dict):raise AccessError('Send a settings object.')
  if data.get('action')=='validate':
   result=settings.public();result['message']='Saved configuration checked locally. No provider connection or message delivery was attempted.'
  elif data.get('action')=='save':
   result=settings.save(data)
   with a.store.connect() as c:a.audit(c,h.identity['id'],'communications_settings_updated','providers')
  else:raise AccessError('Choose a supported settings action.')
  h.respond(200,result)
 except AccessError as e:h.respond(e.status,{'error':str(e)})
 except (ValueError,UnicodeDecodeError):h.respond(400,{'error':'Invalid communications settings request.'})
 except (OSError,psycopg.Error):h.respond(503,{'error':'Communications settings could not be accessed. Retry or contact the server administrator.'})
 return True
