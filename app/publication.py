"""Explicit per-flow publication, separate from draft creation and provider readiness."""
import json,re,os
import psycopg
from urllib.parse import urlsplit
from psycopg import sql
from deployment_config import DeploymentConfig

def state(store,flow,data=None):
 from publication_snapshot import capture,digest,clean,LABELS
 from psycopg.types.json import Jsonb
 with store.connect() as c:
  c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
  exists=c.execute(sql.SQL('SELECT id FROM {} WHERE id=%s AND NOT archived FOR UPDATE').format(sql.Identifier(store.schema,'registration_flows')),(flow,)).fetchone()
  if not exists:raise ValueError('Registration flow not found.')
  table=sql.Identifier(store.schema,'registration_publications')
  row=c.execute(sql.SQL('SELECT published,revision,snapshot,published_at FROM {} WHERE flow_id=%s FOR UPDATE').format(table),(flow,)).fetchone()
  published,revision,old,at=row if row else (False,0,None,None)
  draft=capture(c,store,flow);review=digest(draft)
  changes=[label for key,label in LABELS.items() if old is None or clean(old.get(key))!=clean(draft.get(key))]
  if old and clean(old.get('parent'))!=clean(draft.get('parent')) and 'Event details' not in changes:changes.insert(0,'Event details')
  if data is not None:
   if set(data)-{'published','revision','review_digest'} or type(data.get('published')) is not bool or type(data.get('revision')) is not int or data['revision']!=revision:raise ValueError('Publication changed. Reload and review before trying again.')
   if data['published']:
    if data.get('review_digest')!=review:raise ValueError('Saved drafts changed since review. Review the latest changes before publishing.')
    if draft['footer']['conflict']:raise ValueError('Resolve the shared footer conflict before publishing.')
    if not draft['registration_pages'].get('regtypes'):raise ValueError('Add a registration type before publishing.')
    old=draft;published=True
   else:published=False
   revision+=1
   c.execute(sql.SQL('INSERT INTO {}(flow_id,published,revision,snapshot,snapshot_digest,published_at) VALUES(%s,%s,%s,%s,%s,now()) ON CONFLICT(flow_id) DO UPDATE SET published=excluded.published,revision=excluded.revision,snapshot=excluded.snapshot,snapshot_digest=excluded.snapshot_digest,published_at=CASE WHEN excluded.published THEN now() ELSE {}.published_at END').format(table,table),(flow,published,revision,Jsonb(old),digest(old) if old else None))
   if published:
    from partial_registration import cutoff
    try:expires=cutoff(draft['parent'])
    except ValueError:expires=None
    if expires:c.execute(sql.SQL('UPDATE {} SET expires=%s,token_expires=LEAST(token_expires,%s) WHERE flow_id=%s').format(sql.Identifier(store.schema,'partial_registrations')),(expires,expires,flow))
    else:c.execute(sql.SQL('DELETE FROM {} WHERE flow_id=%s').format(sql.Identifier(store.schema,'partial_registrations')),(flow,))
    changes=[]
  return dict(published=published,revision=revision,review_digest=review,changes=changes,has_changes=bool(changes),published_at=at.isoformat() if at else None)

def enabled(store,flow):
 if os.environ.get('REGFIRE_ENV','local')=='production' and os.environ.get('REGFIRE_PUBLICATION_ENABLED')!='1':return False
 with store.connect() as c:
  return bool(c.execute(sql.SQL('SELECT 1 FROM {} p JOIN {} f ON f.id=p.flow_id WHERE p.flow_id=%s AND p.published AND p.snapshot IS NOT NULL AND NOT f.archived').format(sql.Identifier(store.schema,'registration_publications'),sql.Identifier(store.schema,'registration_flows')),(flow,)).fetchone())

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
 except psycopg.Error:h.respond(409,{'error':'Publication could not be updated. Refresh and review the saved changes before retrying.'})
 return True
