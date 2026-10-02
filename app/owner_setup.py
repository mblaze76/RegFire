"""Private, single-use first-owner bootstrap. The owner email is pinned locally."""
import json,secrets,hmac,threading
from pathlib import Path
from access import AccessError,digest
ROOT=Path(__file__).resolve().parent
POLICY=ROOT/'.local/owner-policy.json'
TOKEN=ROOT/'.local/owner-setup.json'
_lock=threading.Lock()
def owner_email():
 if not POLICY.is_file() or POLICY.stat().st_mode&0o077:raise AccessError('Private owner policy is missing. Ask the local operator to configure it.',503)
 from access import email
 return email(json.loads(POLICY.read_text())['email'])
def prepare(a):
 if a.configured():return
 owner_email()
 with _lock:
  if not TOKEN.exists():
   with open(TOKEN,'x',opener=lambda path,flags:__import__('os').open(path,flags,0o600)) as f:json.dump({'token':secrets.token_urlsafe(32)},f)
def finish(a,token,password):
 with _lock:
  if a.configured():raise AccessError('Owner setup is already complete.',409)
  if not TOKEN.exists() or TOKEN.stat().st_mode&0o077:raise AccessError('Private setup is unavailable.',403)
  expected=json.loads(TOKEN.read_text())['token']
  if not isinstance(token,str) or not hmac.compare_digest(token,expected):raise AccessError('Use the private setup link opened on this computer.',403)
  a.bootstrap(owner_email(),password);TOKEN.unlink(missing_ok=True)
def main():
 import webbrowser
 from database import Store
 from access import Access
 store=Store();store.initialize();a=Access(store)
 if a.configured():raise SystemExit('Owner already configured. Open http://127.0.0.1:8765/login to sign in.')
 prepare(a);token=json.loads(TOKEN.read_text())['token']
 webbrowser.open('http://127.0.0.1:8765/login#setup='+token)
 print('Private owner setup opened in your browser. Set your password there. No password or setup code is printed.')
if __name__=='__main__':main()
