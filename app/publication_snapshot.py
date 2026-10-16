"""Request-local published configuration. Orders, inventory and credentials stay live."""
import copy,hashlib,json
from contextvars import ContextVar
from contextlib import contextmanager
from psycopg import sql
from psycopg.types.json import Jsonb
_current=ContextVar('regfire_publication_snapshot',default=None)
TABLES=('registration_pages','demographics_pages','event_sessions','extra_options','confirmation_pages','membership_settings','payment_preferences')
LABELS={'event':'Event details','welcome':'Shared event branding','footer':'Shared event footer','registration_pages':'Attendee details and registration prices','demographics_pages':'Demographic questions','event_sessions':'Sessions','extra_options':'Additional options','confirmation_pages':'Confirmation layout','membership_settings':'Membership policy','payment_preferences':'Payment preferences and tax'}
def current(store,flow):
 value=_current.get()
 return value[2] if value and value[:2]==(store.schema,str(flow)) else None
@contextmanager
def using(store,flow,snapshot):
 token=_current.set((store.schema,str(flow),snapshot) if snapshot else None)
 try:yield
 finally:_current.reset(token)
def clean(value):
 if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k not in ('updated','created','revision')}
 if isinstance(value,list):return [clean(v) for v in value]
 return value
def digest(value):return hashlib.sha256(json.dumps(clean(value),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def change_details(before,after):
 """Concrete configuration differences; omit operational IDs and secret fields."""
 rows=[]
 hidden={'id','event_id','parent_event_id','updated','created','revision','assets','api','credentials','password','secret','token','api_key','client_secret'}
 def safe(v):
  if isinstance(v,dict):return {k:safe(x) for k,x in v.items() if k not in hidden and not any(s in k.lower() for s in ('password','secret','token','credential'))}
  if isinstance(v,list):return [safe(x) for x in v]
  return v
 def label(k):return {'price_minor':'Price (minor currency units)','regtypes':'Registration types','use_default':'Use default price','visible_to':'Visible registration types','asset_id':'Artwork reference'}.get(k,k.replace('_',' ').capitalize())
 def walk(a,b,path):
  if a==b:return
  if isinstance(a,dict) and isinstance(b,dict):
   for k in sorted(set(a)|set(b)):
    if k in hidden or any(s in k.lower() for s in ('password','secret','token','credential')):continue
    walk(a.get(k),b.get(k),path+[label(k)])
  elif isinstance(a,list) and isinstance(b,list) and all(isinstance(x,dict) and x.get('id') for x in a+b):
   aa={x['id']:x for x in a};bb={x['id']:x for x in b}
   for key in list(aa)+[k for k in bb if k not in aa]:
    item=bb.get(key) or aa[key];name=item.get('name') or item.get('title') or item.get('label') or 'Entry'
    walk(aa.get(key),bb.get(key),path+[name])
   if set(aa)==set(bb) and list(aa)!=list(bb):rows.append(dict(path=' / '.join(path),action='Reordered',before=[x.get('name') or x.get('title') or x.get('label') or 'Entry' for x in a],after=[x.get('name') or x.get('title') or x.get('label') or 'Entry' for x in b]))
  else:rows.append(dict(path=' / '.join(path),action='Added' if a is None else 'Removed' if b is None else 'Changed',before=safe(a),after=safe(b)))
 for key,title in {**LABELS,'parent':'Parent event details'}.items():walk((before or {}).get(key),after.get(key),[title])
 return rows
def capture(c,store,flow):
 def body(table,key,value):
  r=c.execute(sql.SQL('SELECT body FROM {} WHERE {}=%s').format(sql.Identifier(store.schema,table),sql.Identifier(key)),(value,)).fetchone()
  return r[0] if r else None
 event=body('events','id',flow)
 if not event:raise ValueError('Registration flow not found.')
 owner=event.get('parent_event_id',flow);parent=body('events','id',owner)
 result={'event':event,'parent':parent,'welcome':body('welcome_pages','event_id',owner) or {},'footer':body('event_footers','event_id',owner)}
 for table in TABLES:result[table]=body(table,'flow_id' if table=='payment_preferences' else 'event_id',flow)
 # Legacy footer resolution is captured now, never lazily from a later draft.
 if result['footer'] is None:
  from event_footer import normalize
  rows=c.execute(sql.SQL("SELECT p.body->'appearance'->'footer' FROM {} p JOIN {} e ON e.id=p.event_id WHERE e.id=%s OR e.body->>'parent_event_id'=%s").format(store.page_table(),store.table()),(owner,owner)).fetchall()
  empty=normalize({});values={json.dumps(normalize(r[0] or {}),sort_keys=True):normalize(r[0] or {}) for r in rows if normalize(r[0] or {})!=empty}
  result['footer']={'footer':next(iter(values.values())) if len(values)==1 else empty,'conflict':len(values)>1,'legacy':[]}
 from registration import validate_page,starter
 result['registration_pages']=validate_page(result['registration_pages'] or starter(event),event['timezone'])
 from demographics import starter as demo
 result['demographics_pages']=result['demographics_pages'] or demo(flow)
 from sessions import validate as sessions
 result['event_sessions']=sessions(result['event_sessions'] or {'currency':'USD','sessions':[]},parent)
 from extra_options import validate as extras
 result['extra_options']=extras(result['extra_options'] or {})
 from confirmation import validate as confirmation
 result['confirmation_pages']=confirmation(result['confirmation_pages'] or {})
 from membership import starter as member
 result['membership_settings']=result['membership_settings'] or member()
 # Connection secrets and provider assignments are deliberately never snapshotted.
 result['membership_settings'].pop('api',None)
 result['payment_preferences']=result['payment_preferences'] or {}
 assets=set()
 def walk(v,key=''):
  if isinstance(v,dict):
   for k,item in v.items():walk(item,k)
  elif isinstance(v,list):
   for item in v:walk(item,key)
  elif isinstance(v,str) and ('asset_id' in key):assets.add(v)
 walk(result)
 result['assets']={}
 for aid,filename,mime in c.execute(sql.SQL('SELECT id,filename,mime FROM {} WHERE event_id=ANY(%s) AND id=ANY(%s)').format(sql.Identifier(store.schema,'registration_assets')),([flow,owner],list(assets))):result['assets'][str(aid)]=[filename,mime]
 return result

def load(store,flow,*,include_unpublished=False):
 with store.connect() as c:
  r=c.execute(sql.SQL('SELECT snapshot FROM {} WHERE flow_id=%s AND (published OR %s)').format(sql.Identifier(store.schema,'registration_publications')),(flow,include_unpublished)).fetchone()
 return r[0] if r else None

def value(store,flow,key,fallback=None):
 snap=current(store,flow)
 return copy.deepcopy(snap.get(key,fallback)) if snap else fallback

def registration(store,flow):
 snap=current(store,flow)
 if not snap:return None
 page=copy.deepcopy(snap['registration_pages']);footer=footer_value(store,flow)
 if not footer['conflict']:page.setdefault('appearance',{})['footer']=footer['footer']
 from event_theme import apply
 return apply(store,snap['event'],page)

def footer_value(store,flow):
 snap=current(store,flow)
 if not snap:return None
 result=copy.deepcopy(snap['footer']);owner=snap['event'].get('parent_event_id',flow)
 result['footer']['font']=snap['welcome'].get('title_font',snap['welcome'].get('about_font','default'))
 result['footer']['asset_event_id']=owner
 return result|dict(event_id=owner,revision=0)

def page(store,flow,key):
 snap=current(store,flow)
 if not snap:return None
 result=copy.deepcopy(snap[key]);event=snap['event'];owner=event.get('parent_event_id',flow)
 return result|dict(event_id=flow,parent_event_id=owner,event_name=snap['parent']['name'],flow_name=event['name'],timezone=event['timezone'],revision=0)

def backfill(store):
 """Migration-only: preserve exactly the configuration visible before this release."""
 with store.connect() as c:
  c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
  table=sql.Identifier(store.schema,'registration_publications')
  for flow, in c.execute(sql.SQL('SELECT flow_id FROM {} WHERE published AND snapshot IS NULL FOR UPDATE').format(table)).fetchall():
   snap=capture(c,store,str(flow))
   c.execute(sql.SQL('UPDATE {} SET snapshot=%s,snapshot_digest=%s,published_at=now() WHERE flow_id=%s').format(table),(Jsonb(snap),digest(snap),flow))

def public_asset(store,event_id,asset_id):
 """Only captured assets of currently published flows are anonymously readable."""
 with store.connect() as c:
  rows=c.execute(sql.SQL('SELECT p.snapshot FROM {} p JOIN {} f ON f.id=p.flow_id WHERE p.published AND NOT f.archived AND p.snapshot IS NOT NULL').format(sql.Identifier(store.schema,'registration_publications'),sql.Identifier(store.schema,'registration_flows'))).fetchall()
 for snap, in rows:
  if event_id in (snap['event']['id'],snap['event'].get('parent_event_id')) and asset_id in snap['assets']:return snap['assets'][asset_id]
 return None
