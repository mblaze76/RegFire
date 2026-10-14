"""Owner-managed reusable photo connections. No credentials in public responses."""
import uuid
from contextlib import nullcontext
from psycopg import sql
from access import AccessError
import photo_screening as screening

def t(store,name):return sql.Identifier(store.schema,name)
def listing(store):
 with store.connect() as c:
  rows=c.execute(sql.SQL('SELECT id,name,provider,source,secret<>\'\',revision FROM {} ORDER BY name').format(t(store,'photo_profiles'))).fetchall()
  assignments=c.execute(sql.SQL('SELECT event_id,profile_id,revision FROM {}').format(t(store,'photo_profile_assignments'))).fetchall()
 return dict(profiles=[dict(id=str(r[0]),name=r[1],provider=r[2],legacy=r[3]=='legacy',configured=screening.public_status()['configured'] if r[3]=='legacy' else r[4],revision=r[5],live_verified=False) for r in rows],assignments=[dict(event_id=str(r[0]),profile_id=str(r[1]) if r[1] else '',revision=r[2]) for r in assignments],events=[dict(id=e['id'],name=e['name']) for e in store.list()])

def save(store,data):
 ident=str(uuid.UUID(data['id'])) if data.get('id') else str(uuid.uuid4())
 name=data.get('name','')
 if not isinstance(name,str):raise ValueError('Enter a connection name.')
 name=name.strip()
 if not 1<=len(name)<=100:raise ValueError('Enter a connection name up to 100 characters.')
 if data.get('provider','google_vision')!='google_vision':raise ValueError('Only Google Cloud Vision is supported.')
 action=data.get('secret_action','keep');value=data.get('secret','')
 if action not in ('keep','replace','clear'):raise ValueError('Choose keep, replace or clear.')
 if action=='replace' and (not isinstance(value,str) or not 16<=len(value)<=512 or any(not(c.isascii() and (c.isalnum() or c in '_-')) for c in value)):raise ValueError('Enter a valid API key.')
 with store.connect() as c:
  r=c.execute(sql.SQL('SELECT revision,source,secret FROM {} WHERE id=%s FOR UPDATE').format(t(store,'photo_profiles')),(ident,)).fetchone()
  if r and data.get('revision')!=r[0]:raise AccessError('Connection changed. Reload before saving.',409)
  if not r and data.get('id'):raise AccessError('Connection not found.',404)
  source=r[1] if r else 'stored';secret=r[2] if r else ''
  if action!='keep':source='stored';secret=value if action=='replace' else ''
  c.execute(sql.SQL('INSERT INTO {}(id,name,provider,source,secret,revision) VALUES(%s,%s,\'google_vision\',%s,%s,%s) ON CONFLICT(id) DO UPDATE SET name=excluded.name,source=excluded.source,secret=excluded.secret,revision=excluded.revision').format(t(store,'photo_profiles')),(ident,name,source,secret,(r[0]+1) if r else 0))
 return dict(id=ident)

def assign(store,data):
 event=str(uuid.UUID(data.get('event_id','')));profile=str(uuid.UUID(data['profile_id'])) if data.get('profile_id') else None
 with store.connect() as c:
  e=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(store.table()),(event,)).fetchone()
  if not e or e[0].get('parent_event_id'):raise AccessError('Choose a main event.',404)
  if profile and not c.execute(sql.SQL('SELECT 1 FROM {} WHERE id=%s').format(t(store,'photo_profiles')),(profile,)).fetchone():raise AccessError('Connection not found.',404)
  old=c.execute(sql.SQL('SELECT revision FROM {} WHERE event_id=%s').format(t(store,'photo_profile_assignments')),(event,)).fetchone()
  if data.get('revision',0)!=(old[0] if old else 0):raise AccessError('Assignment changed. Reload before saving.',409)
  c.execute(sql.SQL('INSERT INTO {}(event_id,profile_id,revision) VALUES(%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET profile_id=excluded.profile_id,revision=excluded.revision').format(t(store,'photo_profile_assignments')),(event,profile,(old[0]+1) if old else 1))
 return dict(saved=True)

def resolve(store,event,conn=None):
 with (nullcontext(conn) if conn is not None else store.connect()) as c:
  r=c.execute(sql.SQL('SELECT p.id,p.source,p.secret,p.revision,a.revision FROM {} a JOIN {} p ON p.id=a.profile_id WHERE a.event_id=%s FOR SHARE OF p,a').format(t(store,'photo_profile_assignments'),t(store,'photo_profiles')),(event,)).fetchone()
 if not r:raise screening.ScreeningUnavailable('Photo screening is not ready for this event. Contact your administrator.')
 key=screening.credential() if r[1]=='legacy' else r[2]
 if not key:raise screening.ScreeningUnavailable('Photo screening is not ready for this event. Contact your administrator.')
 return key,(str(r[0]),r[3],r[4],screening.revision() if r[1]=='legacy' else '')

def status(store,event):
 try:resolve(store,event);ready=True
 except screening.ScreeningUnavailable:ready=False
 return dict(configured=ready,live_verified=False,message='Photo screening is configured; live service has not been verified.' if ready else 'Photo screening is not ready. Contact your administrator.')


def test_key(store,ident,revision):
 ident=str(uuid.UUID(ident))
 with store.connect() as c:
  row=c.execute(sql.SQL('SELECT source,secret,revision FROM {} WHERE id=%s').format(t(store,'photo_profiles')),(ident,)).fetchone()
 if not row:raise AccessError('Connection not found.',404)
 if revision!=row[2]:raise AccessError('Connection changed. Reload before testing.',409)
 key=screening.credential() if row[0]=='legacy' else row[1]
 if not key:raise screening.ScreeningUnavailable('No credential configured for this connection.')
 return key
