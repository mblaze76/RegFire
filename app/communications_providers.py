"""Provider adapters. Only an explicitly enabled server may contact a delivery provider."""
import base64, json, os, re, ssl
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler
from urllib.parse import urlencode

class DeliveryError(Exception):
 pass

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

class HTTPSClient:
 def request(self,url,body,headers):
  # Fixed provider endpoints only; no redirects or environment proxies carrying credentials.
  req=Request(url,data=body,headers=headers,method='POST')
  try:
   with build_opener(ProxyHandler({}),HTTPSHandler(context=ssl.create_default_context()),NoRedirect()).open(req,timeout=10) as response:
    payload=response.read(65537)
    if len(payload)>65536:raise DeliveryError('Provider response exceeded the limit.')
    return response.status,dict(response.headers),payload
  except Exception:raise DeliveryError('The provider did not confirm submission.') from None

class SendGridAdapter:
 name='sendgrid';channel='email'
 def __init__(self,config,client=None):self.c=config;self.client=client or HTTPSClient()
 def submit(self,recipient,subject,body):
  payload={'personalizations':[{'to':[{'email':recipient}]}],'from':{'email':self.c['sender'],'name':self.c['sender_name']},'subject':subject,'content':[{'type':'text/plain','value':body}]}
  status,headers,_=self.client.request('https://api.sendgrid.com/v3/mail/send',json.dumps(payload).encode(),{'Authorization':'Bearer '+self.c['api_key'],'Content-Type':'application/json'})
  if status!=202:raise DeliveryError('The provider did not accept the email.')
  return {'status':'submitted','provider_id':next((v for k,v in headers.items() if k.lower()=='x-message-id'),None)}

class TwilioAdapter:
 name='twilio';channel='sms'
 def __init__(self,config,client=None):self.c=config;self.client=client or HTTPSClient()
 def submit(self,recipient,subject,body):
  sid=self.c['account_sid'];auth=base64.b64encode((sid+':'+self.c['auth_token']).encode()).decode()
  status,_,payload=self.client.request('https://api.twilio.com/2010-04-01/Accounts/'+sid+'/Messages.json',urlencode({'To':recipient,'From':self.c['sender'],'Body':body}).encode(),{'Authorization':'Basic '+auth,'Content-Type':'application/x-www-form-urlencoded'})
  try:
   data=json.loads(payload)
   if status!=201 or not isinstance(data.get('sid'),str):raise ValueError()
   return {'status':'submitted','provider_id':data['sid']}
  except (ValueError,TypeError):raise DeliveryError('The provider did not accept the SMS.') from None

class BirdAdapter:
 name='bird'
 def __init__(self,config,client=None):self.c=config;self.client=client or HTTPSClient()
 def _submit(self,payload):
  if os.environ.get('REGFIRE_COMMUNICATIONS_LIVE')!='1':raise DeliveryError('Live communications delivery is disabled on this server.')
  key=self.c.get('api_key' if self.channel=='email' else 'auth_token','')
  match=re.fullmatch(r'bk_(us1|eu1)_[A-Za-z0-9_-]{16,}',key)
  if not match:raise DeliveryError('Configure a real regional Bird API key privately.')
  url='https://'+match[1]+'.platform.bird.com/v1/'+self.channel+'/messages'
  status,_,raw=self.client.request(url,json.dumps(payload).encode(),{'Authorization':'Bearer '+key,'Content-Type':'application/json'})
  try:
   data=json.loads(raw)
   if status!=202 or not isinstance(data,dict) or not isinstance(data.get('id'),str) or not data['id'] or data.get('status') not in ('accepted','queued','scheduled'):raise ValueError()
   return {'status':'submitted','provider_id':data['id']}
  except (ValueError,TypeError,UnicodeDecodeError):raise DeliveryError('Bird did not confirm message acceptance.') from None

class BirdEmailAdapter(BirdAdapter):
 channel='email'
 def submit(self,recipient,subject,body):
  return self._submit({'from':{'email':self.c['sender'],'name':self.c['sender_name']},'to':[recipient],'subject':subject,'text':body})

class BirdSMSAdapter(BirdAdapter):
 channel='sms'
 def submit(self,recipient,subject,body,*,category='transactional'):
  if category not in ('transactional','marketing','authentication','service'):raise DeliveryError('Choose a valid SMS category.')
  return self._submit({'from':self.c['sender'],'to':recipient,'text':body,'category':category})
 def submit_otp(self,recipient,code):
  # Transport only: caller must generate, expire and verify the code securely.
  if not isinstance(code,str) or not re.fullmatch(r'[0-9]{4,10}',code):raise DeliveryError('Supply a valid verification code.')
  return self._submit({'to':recipient,'template':{'slug':'bird_otp_verification','parameters':{'code':code}}})

ADAPTERS={'sendgrid':SendGridAdapter,'twilio':TwilioAdapter,'bird':BirdEmailAdapter}

def adapter_for(channel,config,client=None):
 if config['provider']=='bird':return (BirdEmailAdapter if channel=='email' else BirdSMSAdapter)(config,client)
 return ADAPTERS[config['provider']](config,client)

class CommunicationsRecoveryMailer:
 """Keep PasswordRecovery's one-use token workflow; replace only its transport."""
 def __init__(self,settings):self.settings=settings
 @property
 def base_url(self):return self.settings.read()['public_url']
 @property
 def configured(self):
  return os.environ.get('REGFIRE_COMMUNICATIONS_LIVE')=='1' and not self.errors
 @property
 def errors(self):
  c=self.settings.read();errors=self.settings.issues(c,'email')
  if not c['public_url']:errors.append('A recovery site URL is required.')
  if os.environ.get('REGFIRE_COMMUNICATIONS_LIVE')!='1':errors.append('Live communications delivery is disabled on this server.')
  return errors
 def send(self,address,link):
  if not self.configured:raise DeliveryError('Email delivery is disabled.')
  c=self.settings.read()
  if c['email']['provider']=='smtp':
   from password_recovery import SMTPMailer
   return SMTPMailer().send(address,link)
  adapter_for('email',c['email']).submit(address,'Reset your RegFire password','A password reset was requested for your RegFire account.\n\n'+link+'\n\nThis one-use link expires in 30 minutes. If you did not request it, ignore this message. Your password has not changed.\n')

class RecoveryTransport:
 """Preserve existing SMTP activation until an owner saves shared communications settings."""
 def __init__(self,settings):self.settings=settings
 def current(self):
  if self.settings.path.exists():return CommunicationsRecoveryMailer(self.settings)
  from password_recovery import SMTPMailer
  return SMTPMailer()
 @property
 def configured(self):return self.current().configured
 @property
 def errors(self):return self.current().errors
 @property
 def base_url(self):
  return self.current().base_url
 def send(self,address,link):return self.current().send(address,link)
