"""Private local communications configuration, never returned as an API object."""
import copy, fcntl, json, os, re, stat, tempfile, uuid
from pathlib import Path
from urllib.parse import urlsplit
from access import AccessError

DEFAULT={'revision':'initial','public_url':'','email':{'provider':'bird','sender':'','sender_name':'RegFire','api_key':''},'sms':{'provider':'bird','account_sid':'','sender':'','auth_token':''}}

class Settings:
 def __init__(self,path=None):self.path=Path(path) if path else Path(__file__).resolve().parent/'.local'/'communications.json'
 def read(self):
  if not self.path.exists():return copy.deepcopy(DEFAULT)
  if self.path.is_symlink() or stat.S_IMODE(self.path.stat().st_mode)&0o077:raise AccessError('Communications settings require private server file permissions.',503)
  try:
   value=json.loads(self.path.read_text())
   if not isinstance(value,dict) or any(k not in value for k in DEFAULT):raise ValueError()
   if not isinstance(value['revision'],str) or not isinstance(value['public_url'],str):raise ValueError()
   for channel in ('email','sms'):
    if not isinstance(value[channel],dict) or any(not isinstance(value[channel].get(k),str) for k in DEFAULT[channel]):raise ValueError()
   if value['email']['provider'] not in ('bird','sendgrid','smtp') or value['sms']['provider'] not in ('bird','twilio'):raise ValueError()
   return value
  except (ValueError,OSError):raise AccessError('Communications settings are unavailable. Contact the server administrator.',503) from None
 def issues(self,c,channel):
  part=c[channel];issues=[]
  if part['provider']=='bird':
   secret=part['api_key' if channel=='email' else 'auth_token']
   if not re.fullmatch(r'bk_(us1|eu1)_[A-Za-z0-9_-]{16,}',secret):issues.append('Replace bk_xxxxxxxxx with your real Bird API key (bk_us1_… or bk_eu1_…).')
   if not part['sender']:issues.append('Add a verified sender email.' if channel=='email' else 'Add your Bird sending number for free-text SMS.')
   return issues
  if channel=='email':
   if part['provider']=='smtp':
    from password_recovery import SMTPMailer
    return list(SMTPMailer().errors)
   if not part['api_key']:issues.append('Add a SendGrid API key.')
   if not part['sender']:issues.append('Add a verified sender email.')
  else:
   if not part['account_sid']:issues.append('Add a Twilio account SID.')
   if not part['auth_token']:issues.append('Add a Twilio auth token.')
   if not part['sender']:issues.append('Add a Twilio sending number.')
  return issues
 def public(self):
  c=self.read();return {'revision':c['revision'],'public_url':c['public_url'],'delivery_enabled':False,'connection_status':'Not tested with a live provider','email':{'provider':c['email']['provider'],'sender':c['email']['sender'],'sender_name':c['email']['sender_name'],'secret_stored':bool(c['email']['api_key']),'issues':self.issues(c,'email')},'sms':{'provider':c['sms']['provider'],'account_sid':c['sms']['account_sid'],'sender':c['sms']['sender'],'secret_stored':bool(c['sms']['auth_token']),'issues':self.issues(c,'sms')},'recovery_delivery_enabled':os.environ.get('REGFIRE_COMMUNICATIONS_LIVE')=='1'}
 def save(self,data):
  if not isinstance(data,dict):raise AccessError('Send a settings object.')
  self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  if self.path.parent.is_symlink() or stat.S_IMODE(self.path.parent.stat().st_mode)&0o077:raise AccessError('Communications settings require a private server directory.',503)
  # Separate lock survives atomic replacement and protects multiple server processes.
  lock=self.path.with_suffix('.lock')
  fd=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'w') as handle:
   fcntl.flock(handle,fcntl.LOCK_EX)
   c=self.read()
   if data.get('revision')!=c['revision']:raise AccessError('Settings changed. Reload before replacing them.',409)
   for channel,allowed in [('email',{'bird','sendgrid','smtp'}),('sms',{'bird','twilio'})]:
    part=data.get(channel)
    if not isinstance(part,dict) or part.get('provider') not in allowed:raise AccessError('Choose a supported provider.')
    previous_provider=c[channel]['provider']
    c[channel]['provider']=part['provider']
    for key in (('sender','sender_name') if channel=='email' else ('sender','account_sid')):
     value=part.get(key,'')
     if not isinstance(value,str) or len(value)>254 or any(ord(x)<32 for x in value):raise AccessError('Sender details must be short single-line text.')
     c[channel][key]=value.strip()
    secret='api_key' if channel=='email' else 'auth_token'
    action=part.get('secret_action','keep')
    if action not in ('keep','replace','clear'):raise AccessError('Choose keep, replace, or clear credentials.')
    if previous_provider!=part['provider'] and 'bird' in (previous_provider,part['provider']):c[channel][secret]=''
    if action=='clear':c[channel][secret]=''
    elif action=='replace':
     value=part.get('secret')
     if not isinstance(value,str) or not 16<=len(value)<=512 or not re.fullmatch(r'[A-Za-z0-9._-]+',value):raise AccessError('Enter a valid provider credential in the private credential field.')
     if part['provider']=='bird' and not re.fullmatch(r'bk_(us1|eu1)_[A-Za-z0-9_-]{16,}',value):raise AccessError('Replace bk_xxxxxxxxx with your real regional Bird API key.')
     c[channel][secret]=value
   if c['email']['sender'] and not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+',c['email']['sender']):raise AccessError('Enter a plain sender email address.')
   if c['sms']['sender'] and not re.fullmatch(r'\+[1-9][0-9]{7,14}',c['sms']['sender']):raise AccessError('Use an international sending number, such as +15555550100.')
   if c['sms']['provider']=='twilio' and c['sms']['account_sid'] and not re.fullmatch(r'AC[0-9a-fA-F]{32}',c['sms']['account_sid']):raise AccessError('Enter a valid Twilio account SID.')
   origin=data.get('public_url','')
   if not isinstance(origin,str) or len(origin)>500:raise AccessError('Enter a valid recovery site URL.')
   origin=origin.rstrip('/')
   if origin:
    try:
     p=urlsplit(origin)
     if (p.scheme!='https' and not (p.scheme=='http' and p.hostname in ('localhost','127.0.0.1'))) or not p.hostname or p.username or p.password or p.path or p.query or p.fragment or any(x.isspace() for x in origin):raise ValueError()
     p.port
    except ValueError:raise AccessError('Use the HTTPS site origin; HTTP is allowed only for local testing.') from None
   c['public_url']=origin;c['revision']=str(uuid.uuid4())
   temp=None
   try:
    with tempfile.NamedTemporaryFile(mode='w',dir=self.path.parent,prefix='.communications-',delete=False) as stream:
     temp=Path(stream.name);os.chmod(temp,0o600);json.dump(c,stream);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,self.path)
   finally:
    if temp and temp.exists():temp.unlink()
  return self.public()
