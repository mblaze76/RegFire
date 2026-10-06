"""Mailbox recovery. Tokens never enter logs, URLs' query strings, or durable mail queues."""
import os, re, secrets, queue, threading, smtplib, ssl, json
from pathlib import Path
from email.message import EmailMessage
from urllib.parse import urlsplit
from access import AccessError, digest, email, password_hash

GENERIC = 'If this account is eligible, a password reset link will arrive shortly. Check your inbox and spam folder, or contact your administrator.'

class SMTPMailer:
 def __init__(self, env=None):
  config_error=False
  if env is None:
   settings=Path(__file__).resolve().parent/'.local'/'recovery-mail.json'
   try:
    local=json.loads(settings.read_text()) if settings.exists() else {}
    if not isinstance(local,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in local.items()):raise ValueError()
   except (OSError,ValueError):local={};config_error=True
   env={**local,**os.environ}
  else:env=dict(env)
  self.host = env.get('REGFIRE_SMTP_HOST', '')
  self.username = env.get('REGFIRE_SMTP_USERNAME', '')
  self.password = env.get('REGFIRE_SMTP_PASSWORD', '')
  self.sender = env.get('REGFIRE_SMTP_FROM', '')
  self.base_url = env.get('REGFIRE_PUBLIC_URL', '').rstrip('/')
  self.security = env.get('REGFIRE_SMTP_SECURITY', 'ssl')
  self.errors = ['Private recovery-mail.json must contain a JSON object of string settings.'] if config_error else []
  for key, value in [('REGFIRE_SMTP_HOST',self.host),('REGFIRE_SMTP_FROM',self.sender),('REGFIRE_PUBLIC_URL',self.base_url)]:
   if not value:self.errors.append(key+' is required.')
  try:
   parsed=urlsplit(self.base_url)
   if (parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1'))) or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or any(c.isspace() for c in self.base_url):raise ValueError()
   parsed.port
  except ValueError:self.errors.append('REGFIRE_PUBLIC_URL must be a canonical HTTPS origin (HTTP loopback allowed for local testing).')
  try:
   if self.sender!=self.sender.strip():raise AccessError('Invalid sender')
   email(self.sender)
  except AccessError:self.errors.append('REGFIRE_SMTP_FROM must be a plain email address.')
  if self.security not in ('ssl','starttls'):self.errors.append('REGFIRE_SMTP_SECURITY must be ssl or starttls.')
  try:
   self.port=int(env.get('REGFIRE_SMTP_PORT','465' if self.security=='ssl' else '587'))
   if not 1<=self.port<=65535:raise ValueError()
  except ValueError:self.errors.append('REGFIRE_SMTP_PORT is invalid.');self.port=465
  if bool(self.username)!=bool(self.password):self.errors.append('Set both REGFIRE_SMTP_USERNAME and REGFIRE_SMTP_PASSWORD, or neither for a trusted relay.')
  self.configured=not self.errors
 def send(self, address, link):
  message=EmailMessage();message['Subject']='Reset your RegFire password';message['From']=self.sender;message['To']=address
  message.set_content('A password reset was requested for your RegFire account.\n\n'+link+'\n\nThis one-use link expires in 30 minutes. If you did not request it, ignore this message. Your password has not changed.\n')
  context=ssl.create_default_context()
  transport=smtplib.SMTP_SSL if self.security=='ssl' else smtplib.SMTP
  kwargs={'context':context} if self.security=='ssl' else {}
  with transport(self.host,self.port,timeout=10,**kwargs) as smtp:
   if self.security=='starttls':smtp.ehlo();smtp.starttls(context=context);smtp.ehlo()
   if self.username:smtp.login(self.username,self.password)
   smtp.send_message(message)

class PasswordRecovery:
 def __init__(self, access, mailer=None):
  self.a=access;self.mailer=mailer if mailer is not None else SMTPMailer()
  self.jobs=queue.Queue(maxsize=100);self.worker=None;self.lock=threading.Lock()
 def status(self):
  return dict(configured=self.mailer.configured,delivery_verified=False,issues=self.mailer.errors,
   message='Email transport configured; end-to-end delivery has not been verified.' if self.mailer.configured else 'Email recovery is not configured. Administrator reset codes remain available.')
 def limit(self,key,maximum,seconds):
  # Committed independently so rejected attempts cannot roll the counter back.
  with self.a.store.connect() as c:
   c.execute(self.a.q("DELETE FROM {} WHERE window_start < now()-interval '1 day'",'recovery_limits'))
   row=c.execute(self.a.q("INSERT INTO {} AS limits(key_hash,attempts) VALUES(%s,1) ON CONFLICT(key_hash) DO UPDATE SET attempts=CASE WHEN limits.window_start < now()-(%s * interval '1 second') THEN 1 ELSE limits.attempts+1 END, window_start=CASE WHEN limits.window_start < now()-(%s * interval '1 second') THEN now() ELSE limits.window_start END RETURNING attempts",'recovery_limits'),(digest(key),seconds,seconds)).fetchone()
  return row[0]<=maximum
 def request(self,address,source):
  if not self.limit('request-ip:'+source,20,900):raise AccessError('Too many recovery requests. Try again in 15 minutes.',429)
  try:address=email(address)
  except AccessError:return GENERIC
  if not self.limit('request-email:'+address,3,3600):return GENERIC
  if not self.limit('request-global',200,3600) or not self.mailer.configured:return GENERIC
  # Every well-formed address is queued, so account existence doesn't affect response latency.
  with self.lock:
   if self.worker is None:
    self.worker=threading.Thread(target=self._work,daemon=True,name='regfire-password-mail');self.worker.start()
  try:self.jobs.put_nowait(address)
  except queue.Full:pass
  return GENERIC
 def _work(self):
  while True:
   address=self.jobs.get()
   try:
    if address is None:return
    self.deliver(address)
   except Exception:
    # Never log SMTP responses, credentials, addresses or reset links.
    pass
   finally:self.jobs.task_done()
 def close(self):
  if self.worker:
   self.jobs.put(None);self.worker.join(timeout=15)
 def deliver(self,address):
  raw=secrets.token_urlsafe(32)
  with self.a.store.connect() as c:
   row=c.execute(self.a.q("SELECT id,email FROM {} WHERE email=%s AND status='active' AND role!='owner' AND password_hash IS NOT NULL FOR UPDATE",'users'),(address,)).fetchone()
   if not row:return
   uid,recipient=row
   c.execute(self.a.q('DELETE FROM {} WHERE user_id=%s AND expires<=now()','password_resets'),(uid,))
   c.execute(self.a.q("INSERT INTO {}(token_hash,user_id,expires) VALUES(%s,%s,now()+interval '30 minutes')",'password_resets'),(digest(raw),uid))
   self.a.audit(c,uid,'password_reset_requested',uid)
  try:self.mailer.send(recipient,self.mailer.base_url+'/login#reset='+raw)
  except Exception:
   with self.a.store.connect() as c:
    c.execute(self.a.q('DELETE FROM {} WHERE token_hash=%s','password_resets'),(digest(raw),))
    self.a.audit(c,uid,'password_reset_email_failed',uid)
   return
  with self.a.store.connect() as c:self.a.audit(c,uid,'password_reset_email_submitted',uid)
 def complete(self,token,password,source):
  if not self.limit('redeem-ip:'+source,20,900):raise AccessError('Too many recovery attempts. Try again in 15 minutes.',429)
  invalid='Invalid or expired reset link. Request a new link or ask your administrator for a reset code.'
  if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise AccessError(invalid)
  encoded=password_hash(password)
  with self.a.store.connect() as c:
   # Lock the user first, then re-read the token after any concurrent redemption.
   row=c.execute(self.a.q("SELECT u.id FROM {} u JOIN {} r ON r.user_id=u.id WHERE r.token_hash=%s AND u.status='active' AND u.role!='owner' FOR UPDATE OF u",'users','password_resets'),(digest(token),)).fetchone()
   if not row:raise AccessError(invalid)
   valid=c.execute(self.a.q('SELECT 1 FROM {} WHERE token_hash=%s AND expires>now() FOR UPDATE','password_resets'),(digest(token),)).fetchone()
   if not valid:raise AccessError(invalid)
   uid=row[0]
   c.execute(self.a.q('UPDATE {} SET password_hash=%s,email_verified_at=now(),updated=now() WHERE id=%s','users'),(encoded,uid))
   for table in ('password_resets','enrollments','sessions'):c.execute(self.a.q('DELETE FROM {} WHERE user_id=%s',table),(uid,))
   self.a.audit(c,uid,'password_reset_completed',uid)
