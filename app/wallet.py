"""Private wallet configuration and locally signed pass issuance; no account creation."""
import copy,fcntl,hashlib,io,json,os,re,stat,tempfile,time,uuid,zipfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding,rsa,ec
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID
from access import AccessError
ROOT=Path(__file__).parent
DEFAULT={'revision':'initial','apple':{'enabled':False,'pass_type':'','team_id':'','organization':'RegFire','certificate':'','private_key':'','wwdr_certificate':''},'google':{'enabled':False,'issuer_id':'','class_id':'','service_account':''}}
SECRETS={'apple':('certificate','private_key','wwdr_certificate'),'google':('service_account',)}
class Settings:
 def __init__(self,path=None):self.path=Path(path) if path else ROOT/'.local/wallet.json'
 def read(self):
  if not self.path.exists():return copy.deepcopy(DEFAULT)
  if self.path.is_symlink() or stat.S_IMODE(self.path.stat().st_mode)&0o077:raise AccessError('Wallet settings require private permissions.',503)
  return json.loads(self.path.read_text())
 def public(self):
  data=self.read()
  for provider in ('apple','google'):
   part=data[provider];part['issues']=issues(provider,part);part['stored']={k:bool(part.pop(k,'')) for k in SECRETS[provider]}
  data['message']='Local configuration checks only. No live pass has been verified on a device.';return data
 def save(self,data):
  self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  if self.path.parent.is_symlink() or stat.S_IMODE(self.path.parent.stat().st_mode)&0o077:raise AccessError('Wallet settings directory must be private.',503)
  fd=os.open(self.path.with_suffix('.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'w') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX);saved=self.read()
   if data.get('revision')!=saved['revision']:raise ValueError('Wallet settings changed. Reload before saving.')
   for provider,fields in [('apple',('pass_type','team_id','organization')),('google',('issuer_id','class_id'))]:
    part=data.get(provider)
    if not isinstance(part,dict):raise ValueError('Send both wallet configurations.')
    if type(part.get('enabled')) is not bool:raise ValueError('Choose whether issuance is enabled.')
    target=saved[provider];target['enabled']=part['enabled']
    for k in fields:
     v=part.get(k,'')
     if not isinstance(v,str) or len(v)>200 or any(ord(c)<32 for c in v):raise ValueError('Enter short single-line wallet details.')
     target[k]=v.strip()
    for k in SECRETS[provider]:
     action=part.get(k+'_action','keep')
     if action=='clear':target[k]=''
     elif action=='replace':
      v=part.get(k)
      if not isinstance(v,str) or not 1<=len(v)<=20000:raise ValueError('Enter the provider-issued private configuration.')
      target[k]=v
     elif action!='keep':raise ValueError('Choose keep, replace or clear.')
    if target['enabled']:
     errors=issues(provider,target)
     if errors:raise ValueError(' '.join(errors))
   saved['revision']=str(uuid.uuid4());fd,tmp=tempfile.mkstemp(dir=self.path.parent,prefix='.wallet-')
   try:
    with os.fdopen(fd,'w') as f:json.dump(saved,f);f.flush();os.fsync(f.fileno())
    os.replace(tmp,self.path)
   finally:
    if os.path.exists(tmp):os.unlink(tmp)
  return self.public()
def apple_material(c):
 cert=x509.load_pem_x509_certificate(c['certificate'].encode());intermediate=x509.load_pem_x509_certificate(c['wwdr_certificate'].encode());key=serialization.load_pem_private_key(c['private_key'].encode(),None);now=datetime.now(timezone.utc)
 for item in (cert,intermediate):
  if not item.not_valid_before_utc<=now<item.not_valid_after_utc:raise ValueError('Certificate expired or not yet valid.')
 if cert.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)!=key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo):raise ValueError('Private key does not match certificate.')
 def subject(oid):return [v.value for v in cert.subject.get_attributes_for_oid(oid)]
 if c['pass_type'] not in subject(NameOID.USER_ID) or c['team_id'] not in subject(NameOID.ORGANIZATIONAL_UNIT_NAME):raise ValueError('Certificate identifiers do not match.')
 if cert.issuer!=intermediate.subject:raise ValueError('Certificate issuer does not match WWDR.')
 pub=intermediate.public_key()
 if isinstance(pub,rsa.RSAPublicKey):pub.verify(cert.signature,cert.tbs_certificate_bytes,padding.PKCS1v15(),cert.signature_hash_algorithm)
 else:pub.verify(cert.signature,cert.tbs_certificate_bytes,ec.ECDSA(cert.signature_hash_algorithm))
 return cert,key,intermediate

def google_material(c):
 data=json.loads(c['service_account'])
 if data.get('type')!='service_account' or not re.fullmatch(r'[^\s@]+@[^\s@]+\.iam\.gserviceaccount\.com',data.get('client_email','')):raise ValueError('Use a Google service account JSON file.')
 key=serialization.load_pem_private_key(data['private_key'].encode(),None)
 if not isinstance(key,rsa.RSAPrivateKey):raise ValueError('Use the RSA service account key.')
 return data

def issues(provider,c):
 result=[]
 if not c.get('enabled'):result.append('Issuance is disabled.')
 if provider=='apple':
  if not re.fullmatch(r'pass\.[A-Za-z0-9.-]+',c.get('pass_type','')):result.append('Add the Apple Pass Type ID.')
  if not re.fullmatch(r'[A-Z0-9]{10}',c.get('team_id','')):result.append('Add your Apple Team ID.')
  if not c.get('organization'):result.append('Add the issuing organization.')
  if any(not c.get(k) for k in SECRETS['apple']):result.append('Add the pass certificate, matching private key and Apple WWDR certificate.')
  else:
   try:apple_material(c)
   except Exception:result.append('Apple signing material is invalid, expired, or does not match the identifiers.')
 else:
  if not re.fullmatch(r'\d+',c.get('issuer_id','')):result.append('Add the Google Wallet issuer ID.')
  if not re.fullmatch(re.escape(c.get('issuer_id',''))+r'\.[A-Za-z0-9_-]+',c.get('class_id','')):result.append('Add an existing generic pass class ID under this issuer.')
  try:google_material(c)
  except Exception:result.append('Add valid service-account JSON with its private key; grant it issuer access in Google Wallet.')
 return result

def pass_data(doc,c):
 if doc['sample'] or doc['sandbox'] or doc['status'] not in ('paid','confirmed_free'):raise ValueError('Only completed live registrations can issue a wallet pass.')
 details=doc['quote']['details'];name=' '.join(str(x['value']) for x in details if x['label'].lower() in ('first name','last name','name')) or 'Registered attendee'
 return {'formatVersion':1,'passTypeIdentifier':c['pass_type'],'serialNumber':doc['confirmation_id'],'teamIdentifier':c['team_id'],'organizationName':c['organization'],'description':doc['event']['name']+' registration','logoText':'Registration. Reignited.','foregroundColor':'rgb(255,255,255)','backgroundColor':'rgb(36,36,43)','labelColor':'rgb(255,185,120)','barcodes':[{'format':'PKBarcodeFormatQR','message':doc['qr_payload'],'messageEncoding':'utf-8'}],'eventTicket':{'primaryFields':[{'key':'event','label':'EVENT','value':doc['event']['name']}],'secondaryFields':[{'key':'attendee','label':'ATTENDEE','value':name}],'auxiliaryFields':[{'key':'start','label':'START','value':doc['event'].get('start','')},{'key':'venue','label':'VENUE','value':doc['event'].get('venue','')}],'backFields':[{'key':'event_id','label':'Event ID','value':doc['event_id']},{'key':'confirmation_id','label':'Confirmation ID','value':doc['confirmation_id']}]}}

def apple_pass(doc,c):
 if issues('apple',c):raise ValueError('Apple Wallet is not ready.')
 from PIL import Image
 payload=pass_data(doc,c);cert,key,wwdr=apple_material(c);files={'pass.json':json.dumps(payload).encode()}
 for filename,size in [('icon.png',29),('icon@2x.png',58),('icon@3x.png',87),('logo.png',80),('logo@2x.png',160)]:
  with Image.open(ROOT/'static/regfire-logo-3d-transparent.png') as image:
   image.thumbnail((size,size));stream=io.BytesIO();image.save(stream,'PNG');files[filename]=stream.getvalue()
 manifest=json.dumps({k:hashlib.sha1(v).hexdigest() for k,v in files.items()},sort_keys=True).encode();files['manifest.json']=manifest
 files['signature']=pkcs7.PKCS7SignatureBuilder().set_data(manifest).add_signer(cert,key,hashes.SHA256()).add_certificate(wwdr).sign(serialization.Encoding.DER,[pkcs7.PKCS7Options.DetachedSignature,pkcs7.PKCS7Options.Binary])
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
  for name,content in files.items():archive.writestr(name,content)
 return out.getvalue()

def google_url(doc,c):
 if issues('google',c):raise ValueError('Google Wallet is not ready.')
 # Reuse the completion gate and attendee-safe identity extraction.
 apple=pass_data(doc,dict(pass_type='',team_id='',organization='RegFire'))
 import jwt
 account=google_material(c);obj={'id':c['issuer_id']+'.regfire_'+doc['confirmation_id'].replace('-','_'),'classId':c['class_id'],'state':'ACTIVE','cardTitle':{'defaultValue':{'language':'en-US','value':'RegFire'}},'header':{'defaultValue':{'language':'en-US','value':doc['event']['name']}},'subheader':{'defaultValue':{'language':'en-US','value':doc['quote']['regtype']}},'barcode':{'type':'QR_CODE','value':doc['qr_payload']},'textModulesData':[{'id':'attendee','header':'Attendee','body':apple['eventTicket']['secondaryFields'][0]['value']},{'id':'start','header':'Start','body':doc['event'].get('start','') or 'See event details'},{'id':'confirmation','header':'Confirmation','body':doc['confirmation_id']},{'id':'event','header':'Event ID','body':doc['event_id']},{'id':'venue','header':'Venue','body':doc['event'].get('venue','') or 'See event details'}]}
 token=jwt.encode({'iss':account['client_email'],'aud':'google','typ':'savetowallet','iat':int(time.time()),'payload':{'genericObjects':[obj]}},account['private_key'],algorithm='RS256')
 return 'https://pay.google.com/gp/v/save/'+token

def settings(server):return Settings(getattr(server,'wallet_settings_path',None))
def handle(h):
 path=urlsplit(h.path).path
 if path in ('/wallet-settings','/wallet-settings.js') and h.command=='GET':
  from confirmation import send_bytes
  filename='wallet-settings.html' if path=='/wallet-settings' else 'wallet-settings.js';send_bytes(h,(ROOT/'static'/filename).read_bytes(),'text/html' if filename.endswith('.html') else 'text/javascript');return True
 if path!='/api/admin/wallet':return False
 try:
  from communications import require_owner
  from access_http import access
  require_owner(access(h),h.identity);config=settings(h.server)
  if h.command=='GET':result=config.public()
  elif h.command=='POST':
   size=int(h.headers.get('Content-Length',0))
   if not 0<size<=90000:raise ValueError('Wallet settings are missing or too large.')
   data=json.loads(h.rfile.read(size));result=config.save(data)
  else:raise ValueError('Use GET or POST.')
  h.respond(200,result)
 except AccessError as e:h.respond(e.status,{'error':str(e)})
 except (ValueError,TypeError,KeyError):h.respond(400,{'error':'Check wallet settings, identifiers, signing material and revision. No changes were saved.'})
 except OSError:h.respond(503,{'error':'Private wallet settings could not be saved.'})
 return True
