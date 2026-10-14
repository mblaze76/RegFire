"""Explicit per-flow publication, separate from draft creation and provider readiness."""
import json,re,os
from urllib.parse import urlsplit
from psycopg import sql
from deployment_config import DeploymentConfig

def state(store,flow,data=None):
 with store.connect() as c:
  exists=c.execute(sql.SQL('SELECT id FROM {} WHERE id=%s AND NOT archived FOR UPDATE').format(sql.Identifier(store.schema,'registration_flows')),(flow,)).fetchone()
  if not exists:raise ValueError('Registration flow not found.')
  table=sql.Identifier(store.schema,'registration_publications')
  row=c.execute(sql.SQL('SELECT published,revision FROM {} WHERE flow_id=%s').format(table),(flow,)).fetchone()
  result=dict(published=row[0] if row else False,revision=row[1] if row else 0)
  if data is not None:
   if set(data)!={'published','revision'} or type(data['published']) is not bool or type(data['revision']) is not int or data['revision']!=result['revision']:raise ValueError('Publication changed or request is invalid. Reload and try again.')
   if data['published']:
    page=store.registration_page(flow)
    if not page.get('regtypes'):raise ValueError('Add a registration type before publishing.')
   result=dict(published=data['published'],revision=result['revision']+1)
   c.execute(sql.SQL('INSERT INTO {}(flow_id,published,revision) VALUES(%s,%s,%s) ON CONFLICT(flow_id) DO UPDATE SET published=excluded.published,revision=excluded.revision').format(table),(flow,result['published'],result['revision']))
  return result

def enabled(store,flow):
 if os.environ.get('REGFIRE_ENV','local')=='production' and os.environ.get('REGFIRE_PUBLICATION_ENABLED')!='1':return False
 with store.connect() as c:
  return bool(c.execute(sql.SQL('SELECT 1 FROM {} p JOIN {} f ON f.id=p.flow_id WHERE p.flow_id=%s AND p.published AND NOT f.archived').format(sql.Identifier(store.schema,'registration_publications'),sql.Identifier(store.schema,'registration_flows')),(flow,)).fetchone())

def handle(h):
 m=re.fullmatch(r'/api/events/([a-f0-9-]{36})/publication',urlsplit(h.path).path)
 if not m:return False
 try:
  data=None
  if h.command=='POST':
   size=int(h.headers.get('Content-Length',0))
   if not 0<size<=1024:raise ValueError('Invalid publication request.')
   data=json.loads(h.rfile.read(size))
   if not isinstance(data,dict):raise ValueError('Invalid publication request.')
  elif h.command!='GET':raise ValueError('Use GET or POST.')
  value=state(h.server.store,m[1],data);config=DeploymentConfig.load(h.server.server_port)
  value.update(url=config.origin+'/register#event='+m[1]+'&mode=registration',hosted=config.secure_cookies and os.environ.get('REGFIRE_PUBLICATION_ENABLED')=='1',available=enabled(h.server.store,m[1]),notice='Payment preferences are a preview, not a processor connection. Automatic confirmation email delivery is off unless separately enabled by an authorized operator.')
  h.respond(200,value)
 except (ValueError,TypeError,KeyError) as e:h.respond(400,{'error':str(e)})
 return True
