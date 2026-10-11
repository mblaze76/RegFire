"""Local corporate preview with server-side protection for all investor assets.
Production hosting must enforce equivalent protection; this is not a Netlify configuration.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse,base64,hashlib,hmac,json,os
ROOT=Path(__file__).resolve().parents[1]
DIST=(ROOT/'dist').resolve()
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(DIST),**kwargs)
 def protected(self):
  target=Path(self.translate_path(self.path)).resolve()
  return target==DIST/'investors' or DIST/'investors' in target.parents
 def authorized(self):
  if not self.protected():return True
  credential=self.headers.get('Authorization','')
  valid=False
  if credential.startswith('Basic '):
   try:
    _,password=base64.b64decode(credential[6:],validate=True).decode().split(':',1)
    valid=hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(),self.server.password_hash)
   except (ValueError,UnicodeError):pass
  if valid:return True
  self.send_response(401);self.send_header('WWW-Authenticate','Basic realm="RegFire Investors", charset="UTF-8"');self.send_header('Cache-Control','no-store');self.end_headers()
  if self.command!='HEAD':self.wfile.write(b'Investor access requires the approved password.')
  return False
 def do_GET(self):
  if self.authorized():super().do_GET()
 def do_HEAD(self):
  if self.authorized():super().do_HEAD()
 def end_headers(self):
  if self.protected():self.send_header('Cache-Control','private, no-store');self.send_header('X-Robots-Tag','noindex, noarchive')
  super().end_headers()
 def list_directory(self,path):self.send_error(403,'Directory listing is disabled');return None
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8790);a=p.parse_args()
 config=ROOT/'.local/investor-preview.json'
 secret_hash=os.environ.get('REGFIRE_INVESTOR_PASSWORD_HASH','')
 if not secret_hash and config.exists():secret_hash=json.loads(config.read_text()).get('password_sha256','')
 if len(secret_hash)!=64:raise SystemExit('Investor preview password must be configured before starting.')
 server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);server.password_hash=secret_hash;server.serve_forever()
