"""Local shared-workspace identity and product access. No email delivery or mailbox verification."""
import hashlib,hmac,secrets,re,uuid,threading,time
from datetime import datetime,timezone,timedelta
from psycopg import sql

class AccessError(Exception):
 def __init__(self,message,status=400):super().__init__(message);self.status=status

def email(value):
 if not isinstance(value,str) or len(value)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value.strip()):raise AccessError('Enter a valid email address.')
 return value.strip().casefold()
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def password_hash(password,salt=None):
 if not isinstance(password,str) or not 12<=len(password)<=256:raise AccessError('Use a password of 12–256 characters.')
 salt=salt or secrets.token_hex(16)
 hashed=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=2**15,r=8,p=3,maxmem=64*1024*1024).hex()
 return 'scrypt$'+salt+'$'+hashed
def password_ok(password,encoded):
 try:return hmac.compare_digest(password_hash(password,encoded.split('$')[1]),encoded)
 except (ValueError,IndexError,TypeError,AccessError):return False

class Access:
 def __init__(self,store):self.store=store;self.lock=threading.Lock();self.attempts=[]
 def t(self,name):return sql.Identifier(self.store.schema,'access_'+name)
 def q(self,query,*tables):return sql.SQL(query).format(*(self.t(t) for t in tables))
 def audit(self,c,actor,action,target):c.execute(self.q('INSERT INTO {}(actor,action,target) VALUES(%s,%s,%s)','audit'),(actor,action,str(target)))
 def configured(self):
  with self.store.connect() as c:return bool(c.execute(self.q("SELECT 1 FROM {} WHERE role='owner'",'users')).fetchone())
 def bootstrap(self,address,password):
  address=email(address);encoded=password_hash(password);uid=str(uuid.uuid4())
  with self.store.connect() as c:
   c.execute(self.q('LOCK TABLE {} IN EXCLUSIVE MODE','users'))
   if c.execute(self.q('SELECT 1 FROM {} LIMIT 1','users')).fetchone():raise AccessError('An owner already exists. Bootstrap cannot run again.')
   c.execute(self.q("INSERT INTO {}(id,email,password_hash,role,status) VALUES(%s,%s,%s,'owner','active')",'users'),(uid,address,encoded))
   c.execute(self.q("INSERT INTO {} VALUES(%s,'event-builder')",'grants'),(uid,));self.audit(c,uid,'owner_bootstrap',uid)
  return uid
 def throttle(self):
  with self.lock:
   now=time.monotonic();self.attempts=[t for t in self.attempts if now-t<900]
   if len(self.attempts)>=20:raise AccessError('Too many sign-in attempts. Wait 15 minutes before trying again.',429)
   self.attempts.append(now)
 def login(self,address,password):
  self.throttle()
  try:address=email(address)
  except AccessError:address='invalid'
  with self.store.connect() as c:
   row=c.execute(self.q('SELECT id,password_hash,status FROM {} WHERE email=%s FOR UPDATE','users'),(address,)).fetchone()
   encoded=row[1] if row and row[1] else 'scrypt$'+'00'*16+'$'+'00'*64
   valid=password_ok(password,encoded)
   if not row or not valid or row[2]!='active':raise AccessError('Email or password is incorrect, or access is inactive.',401)
   raw=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
   c.execute(self.q('DELETE FROM {} WHERE expires<now()','sessions'))
   c.execute(self.q("INSERT INTO {}(token_hash,user_id,csrf,expires) VALUES(%s,%s,%s,now()+interval '8 hours')",'sessions'),(digest(raw),row[0],csrf));self.audit(c,row[0],'sign_in',row[0])
  return raw
 def session(self,raw):
  if not raw or len(raw)>256:return None
  with self.store.connect() as c:
   row=c.execute(self.q("SELECT u.id,u.email,u.role,s.csrf FROM {} s JOIN {} u ON u.id=s.user_id WHERE s.token_hash=%s AND s.expires>now() AND u.status='active'",'sessions','users'),(digest(raw),)).fetchone()
   if not row:return None
   products=[r[0] for r in c.execute(self.q('SELECT g.product_slug FROM {} g JOIN {} p ON p.slug=g.product_slug WHERE g.user_id=%s AND p.enabled','grants','products'),(row[0],))]
   return dict(id=str(row[0]),email=row[1],role=row[2],csrf=row[3],products=products,email_verified=False)
 def logout(self,raw):
  with self.store.connect() as c:c.execute(self.q('DELETE FROM {} WHERE token_hash=%s','sessions'),(digest(raw),))
 def products(self):
  with self.store.connect() as c:return [dict(slug=r[0],name=r[1],enabled=r[2],available=r[0]=='event-builder',path='/' if r[0]=='event-builder' else None) for r in c.execute(self.q('SELECT slug,name,enabled FROM {} ORDER BY name','products'))]
 def require_admin(self,actor):
  if not actor or actor['role'] not in ('owner','admin'):raise AccessError('Administrator access is required.',403)
 def users(self,actor):
  self.require_admin(actor)
  with self.store.connect() as c:
   rows=c.execute(self.q('SELECT id,email,role,status,password_hash IS NOT NULL,first_name,last_name,company_name FROM {} ORDER BY email','users')).fetchall()
   grants=c.execute(self.q('SELECT user_id,product_slug FROM {}','grants')).fetchall()
   events=c.execute(self.q('SELECT user_id,event_id FROM {}','event_grants')).fetchall()
   return [dict(id=str(r[0]),email=r[1],role=r[2],status=r[3],sign_in_ready=r[4],first_name=r[5],last_name=r[6],company_name=r[7],event_ids=[str(e) for u,e in events if u==r[0]],email_verified=False,products=[p for u,p in grants if u==r[0]]) for r in rows]
 def save_user(self,actor,data):
  self.require_admin(actor);address=email(data.get('email'));role=data.get('role','client');status=data.get('status','assigned');products=data.get('products',[])
  if role=='user':role='client'
  if role not in ('admin','client','employee') or status not in ('assigned','active','suspended'):raise AccessError('Choose a valid role and status.')
  profile={}
  for field in ('first_name','last_name','company_name'):
   value=data.get(field,'')
   if not isinstance(value,str) or len(value.strip())>120:raise AccessError('Profile fields must be text of at most 120 characters.')
   profile[field]=value.strip()
  event_ids=data.get('event_ids')
  if event_ids is not None:
   if not isinstance(event_ids,list) or len(event_ids)>1000:raise AccessError('Choose valid events.')
   try:event_ids=[str(uuid.UUID(v)) for v in event_ids]
   except (ValueError,TypeError,AttributeError):raise AccessError('Choose valid events.')
   if len(set(event_ids))!=len(event_ids):raise AccessError('Choose each event once.')
  if not isinstance(products,list) or len(products)>100 or any(not isinstance(p,str) for p in products) or len(set(products))!=len(products):raise AccessError('Choose valid products.')
  with self.store.connect() as c:
   # Serialize management writes, including concurrent grants and role changes.
   c.execute(self.q('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE','users'))
   current=c.execute(self.q('SELECT role,status FROM {} WHERE id=%s','users'),(actor['id'],)).fetchone()
   if not current or current[1]!='active' or current[0] not in ('owner','admin'):raise AccessError('Administrator access is required.',403)
   row=c.execute(self.q('SELECT id,role,password_hash FROM {} WHERE email=%s FOR UPDATE','users'),(address,)).fetchone()
   if row and row[1]=='owner':raise AccessError('The initial owner cannot be changed here.')
   if row and str(row[0])==actor['id']:raise AccessError('Ask another administrator to change your own account.')
   if current[0]!='owner' and (role=='admin' or (row and row[1]=='admin')):raise AccessError('Only the owner can manage administrators.',403)
   known={r[0] for r in c.execute(self.q('SELECT slug FROM {}','products'))}
   if not set(products)<=known:raise AccessError('A selected product does not exist.')
   if status=='active' and (not row or not row[2]):raise AccessError('This user must set a password with an enrollment code before activation.')
   if event_ids is not None:
    known_events={str(r[0]) for r in c.execute(sql.SQL("SELECT id FROM {} WHERE NOT (body ? 'parent_event_id')").format(self.store.table()))}
    if not set(event_ids)<=known_events:raise AccessError('A selected event is unavailable in this workspace.')
   uid=str(row[0]) if row else str(uuid.uuid4())
   c.execute(self.q('INSERT INTO {}(id,email,role,status) VALUES(%s,%s,%s,%s) ON CONFLICT(email) DO UPDATE SET role=excluded.role,status=excluded.status,updated=now()','users'),(uid,address,role,status))
   for field,value in profile.items():
    if field in data or not row:c.execute(sql.SQL('UPDATE {} SET {}=%s WHERE id=%s').format(self.t('users'),sql.Identifier(field)),(value,uid))
   if event_ids is not None:
    c.execute(self.q('DELETE FROM {} WHERE user_id=%s','event_grants'),(uid,))
    for eid in event_ids:c.execute(self.q('INSERT INTO {}(user_id,event_id) VALUES(%s,%s)','event_grants'),(uid,eid))
   c.execute(self.q('DELETE FROM {} WHERE user_id=%s','grants'),(uid,))
   for p in products:c.execute(self.q('INSERT INTO {} VALUES(%s,%s)','grants'),(uid,p))
   c.execute(self.q('DELETE FROM {} WHERE user_id=%s','sessions'),(uid,))
   c.execute(self.q('DELETE FROM {} WHERE user_id=%s','enrollments'),(uid,));self.audit(c,actor['id'],'user_access_updated',uid)
  return uid
 def save_product(self,actor,data):
  self.require_admin(actor);slug=data.get('slug','');name=data.get('name','');enabled=data.get('enabled',True)
  if not isinstance(slug,str) or not re.fullmatch(r'[a-z][a-z0-9-]{1,49}',slug) or not isinstance(name,str) or not 1<=len(name.strip())<=80 or type(enabled) is not bool:raise AccessError('Use a short product name and a lowercase product ID.')
  with self.store.connect() as c:
   c.execute(self.q('INSERT INTO {}(slug,name,enabled) VALUES(%s,%s,%s) ON CONFLICT(slug) DO UPDATE SET name=excluded.name,enabled=excluded.enabled','products'),(slug,name.strip(),enabled));self.audit(c,actor['id'],'product_updated',slug)
 def enrollment(self,actor,uid):
  self.require_admin(actor)
  try:uid=str(uuid.UUID(uid))
  except (ValueError,TypeError):raise AccessError('Select a user.')
  with self.store.connect() as c:
   row=c.execute(self.q('SELECT role,status FROM {} WHERE id=%s FOR UPDATE','users'),(uid,)).fetchone()
   if not row or row[0]=='owner' or row[1]=='suspended':raise AccessError('Enrollment is unavailable for this account.')
   if row[0]=='admin' and actor['role']!='owner':raise AccessError('Only the owner can enroll administrators.',403)
   raw=secrets.token_urlsafe(32)
   c.execute(self.q("INSERT INTO {}(token_hash,user_id,expires) VALUES(%s,%s,now()+interval '24 hours') ON CONFLICT(user_id) DO UPDATE SET token_hash=excluded.token_hash,expires=excluded.expires",'enrollments'),(digest(raw),uid));self.audit(c,actor['id'],'enrollment_issued',uid)
   return raw
 def activate(self,address,token,password):
  self.throttle();address=email(address);encoded=password_hash(password)
  if not isinstance(token,str) or len(token)>256:raise AccessError('Invalid or expired enrollment code.')
  with self.store.connect() as c:
   row=c.execute(self.q("SELECT u.id FROM {} u JOIN {} e ON e.user_id=u.id WHERE u.email=%s AND e.token_hash=%s AND e.expires>now() AND u.status!='suspended' AND u.role!='owner' FOR UPDATE OF u,e",'users','enrollments'),(address,digest(token))).fetchone()
   if not row:raise AccessError('Invalid or expired enrollment code.')
   c.execute(self.q("UPDATE {} SET password_hash=%s,status='active',updated=now() WHERE id=%s",'users'),(encoded,row[0]))
   c.execute(self.q('DELETE FROM {} WHERE user_id=%s','enrollments'),(row[0],));c.execute(self.q('DELETE FROM {} WHERE user_id=%s','sessions'),(row[0],));self.audit(c,row[0],'password_enrolled',row[0])
 def audit_rows(self,actor):
  self.require_admin(actor)
  with self.store.connect() as c:return [dict(action=r[0],target=r[1],created=r[2].isoformat()) for r in c.execute(self.q('SELECT action,target,created FROM {} ORDER BY id DESC LIMIT 50','audit'))]

 def event_ids(self,actor):
  with self.store.connect() as c:
   return {str(r[0]) for r in c.execute(self.q('SELECT event_id FROM {} WHERE user_id=%s','event_grants'),(actor['id'],))}
 def event_list(self,actor):
  events=self.store.list()
  if actor['role'] in ('owner','admin'):return events
  allowed=self.event_ids(actor)
  return [e for e in events if e['id'] in allowed]
 def require_event(self,actor,event_id):
  try:event_id=str(uuid.UUID(event_id))
  except (ValueError,TypeError):raise AccessError('Event not found.',404)
  with self.store.connect() as c:
   row=c.execute(sql.SQL("SELECT COALESCE(body->>'parent_event_id',id::text) FROM {} WHERE id=%s").format(self.store.table()),(event_id,)).fetchone()
   if not row:raise AccessError('Event not found.',404)
   if actor['role'] in ('owner','admin'):return
   if not c.execute(self.q('SELECT 1 FROM {} WHERE user_id=%s AND event_id=%s','event_grants'),(actor['id'],row[0])).fetchone():raise AccessError('Event not found or not assigned to your account.',404)
