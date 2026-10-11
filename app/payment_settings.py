"""Named, owner-managed payment connections. Secrets never leave this module's public view."""
import copy,fcntl,json,os,re,stat,tempfile,uuid
from pathlib import Path
from urllib.parse import urlsplit

class PaymentSettings:
 def __init__(self,path=None):self.path=Path(path) if path else Path(__file__).parent/'.local'/'payment-connections.json'
 def read(self):
  if not self.path.exists():return dict(revision='initial',connections=[],assignments={})
  if self.path.is_symlink() or stat.S_IMODE(self.path.stat().st_mode)&0o077:raise ValueError('Payment settings require private file permissions.')
  return json.loads(self.path.read_text())
 def public(self):
  data=self.read()
  for c in data['connections']:
   c['stored']={key:bool(c.pop(key,'')) for key in ('secret','client_id','webhook_secret')}
  return data
 def save(self,data):
  self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  if self.path.parent.is_symlink() or stat.S_IMODE(self.path.parent.stat().st_mode)&0o077:raise ValueError('Payment settings directory must be private.')
  fd=os.open(self.path.with_suffix('.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'w') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX);saved=self.read()
   if data.get('revision')!=saved['revision']:raise ValueError('Payment settings changed. Reload before saving.')
   if data.get('action')=='connection':
    incoming=data.get('connection',{});ident=incoming.get('id') or str(uuid.uuid4());ident=str(uuid.UUID(ident));old=next((c for c in saved['connections'] if c['id']==ident),None)
    provider=incoming.get('provider');mode=incoming.get('mode')
    if provider not in ('stripe','paypal') or mode not in ('sandbox','live'):raise ValueError('Choose Stripe or PayPal and sandbox or live.')
    if old and (old['provider']!=provider or old['mode']!=mode):raise ValueError('Create a separate connection for a different provider or mode.')
    name=incoming.get('name','').strip()
    if not 1<=len(name)<=100:raise ValueError('Give the connection a short name.')
    base=incoming.get('return_base','').strip().rstrip('/');u=urlsplit(base)
    if base and (u.username or u.password or u.query or u.fragment or u.path or not u.hostname or (u.scheme!='https' and not(mode=='sandbox' and u.scheme=='http' and u.hostname in ('localhost','127.0.0.1')))):raise ValueError('Use your HTTPS app origin, or localhost HTTP for sandbox testing.')
    c=copy.deepcopy(old) if old else dict(id=ident,secret='',client_id='',webhook_secret='')
    c.update(name=name,provider=provider,mode=mode,return_base=base,enabled=incoming.get('enabled') is True)
    for key in ('secret','client_id','webhook_secret'):
     action=incoming.get(key+'_action','keep')
     if action=='clear':c[key]=''
     elif action=='replace':
      value=incoming.get(key,'')
      if not isinstance(value,str) or not 1<=len(value)<=1024 or re.search(r'\s',value):raise ValueError('Enter a valid private provider value.')
      c[key]=value
     elif action!='keep':raise ValueError('Choose keep, replace, or clear.')
    if provider=='stripe' and c['secret'] and not c['secret'].startswith('sk_test_' if mode=='sandbox' else 'sk_live_'):raise ValueError('Stripe key must match the connection mode.')
    saved['connections']=[x for x in saved['connections'] if x['id']!=ident]+[c]
   elif data.get('action')=='assignment':
    event=str(uuid.UUID(data.get('event_id','')));ids=data.get('connections',[]);valid={c['id'] for c in saved['connections']}
    if not isinstance(ids,list) or any(x not in valid for x in ids) or len(set(ids))!=len(ids):raise ValueError('Choose existing connections.')
    default=data.get('default') or None
    if default and default not in ids:raise ValueError('Default must be one of the assigned connections.')
    tax=data.get('tax_bps')
    if tax is not None and (type(tax) is not int or not 0<=tax<=10000):raise ValueError('Tax must be between 0 and 100 percent, or left unconfigured.')
    saved['assignments'][event]=dict(connections=ids,default=default,tax_bps=tax)
   else:raise ValueError('Choose a supported payment settings action.')
   saved['revision']=str(uuid.uuid4());fd,tmp=tempfile.mkstemp(dir=self.path.parent,prefix='.payment-')
   try:
    with os.fdopen(fd,'w') as file:json.dump(saved,file);file.flush();os.fsync(file.fileno())
    os.replace(tmp,self.path)
   finally:
    if os.path.exists(tmp):os.unlink(tmp)
  return self.public()
 def connection(self,ident):
  c=next((c for c in self.read()['connections'] if c['id']==ident),None)
  if not c:raise ValueError('Payment connection not found.')
  return c

def issues(c):
 result=[]
 if not c.get('enabled'):result.append('Connection is disabled.')
 if not c.get('return_base'):result.append('Add the app return origin.')
 if not c.get('secret'):result.append('Add the private API secret.')
 if c['provider']=='paypal' and not c.get('client_id'):result.append('Add the PayPal client ID.')
 if not c.get('webhook_secret'):result.append('Add the Stripe signing secret or PayPal webhook ID.')
 return result
