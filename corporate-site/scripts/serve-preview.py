"""Local corporate preview with a form-based investor gate.
Production hosting must enforce equivalent protection; not a Netlify configuration.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import argparse, hashlib, hmac, json, os, secrets, time

ROOT = Path(__file__).resolve().parents[1]
DIST = (ROOT / 'dist').resolve()
COOKIE = 'regfire_investor_session'
GATE = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>Investor access | RegFire</title><style>
*{box-sizing:border-box}body{margin:0;min-height:100svh;background:#0b0e16;color:#f7f8fc;font:17px/1.6 system-ui,sans-serif}
header{padding:24px clamp(20px,5vw,72px);border-bottom:1px solid #303643}header img{width:164px;height:auto}
main{max-width:520px;margin:clamp(40px,10vh,110px) auto;padding:0 24px 48px}.eyebrow{color:#ffae73;font-weight:700;letter-spacing:.12em;font-size:13px}
h1{font-size:clamp(28px,5vw,38px);line-height:1.2;margin:12px 0 20px}p{color:#c5cbd6}label{display:block;font-weight:600;margin-bottom:8px}
input,button{font:inherit;width:100%;min-height:52px;border-radius:10px}input{background:#171d2b;color:white;border:1px solid #7d899d;padding:12px 14px}
button{border:0;background:#ff852e;color:#16100b;font-weight:750;margin-top:20px;cursor:pointer}button:hover{background:#ffa45f}
a{color:#e7eaf1;text-underline-offset:4px}a:focus-visible,input:focus-visible,button:focus-visible{outline:3px solid #ffb574;outline-offset:4px}
.error{color:#ffb6aa;margin:12px 0 0}.back{display:inline-block;margin-top:28px}small{display:block;color:#aeb8ca;margin-top:24px}
</style></head><body><header><a href="/" aria-label="RegFire home"><img src="/regfire-logo-3d-transparent.png" alt="RegFire"></a></header>
<main><div class="eyebrow">INVESTORS</div><h1>Please enter your password.</h1><p>Enter the password shared with you to view our investor materials.</p>
<form method="post" action="/investors/unlock"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="256" ERRORATTR>
ERRORMSG<button type="submit">View investor materials</button></form><a class="back" href="/">Back to homepage</a><small>Registration. Reignited.</small></main></body></html>'''

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def protected(self):
        target = Path(self.translate_path(self.path)).resolve()
        return target == DIST / 'investors' or DIST / 'investors' in target.parents

    def authorized(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookie[COOKIE].value if COOKIE in cookie else ''
            return self.server.sessions.get(token, 0) > time.time()
        except Exception:
            return False

    def gate(self, error=False):
        body = GATE.replace('ERRORATTR', 'aria-invalid="true" aria-describedby="password-error"' if error else '')
        body = body.replace('ERRORMSG', '<p id="password-error" class="error" role="alert">That password was not recognized. Please try again.</p>' if error else '')
        data = body.encode()
        self.send_response(401 if error else 200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        if self.command != 'HEAD': self.wfile.write(data)

    def do_GET(self):
        if self.protected() and not self.authorized(): self.gate()
        else: super().do_GET()

    def do_HEAD(self):
        if self.protected() and not self.authorized(): self.gate()
        else: super().do_HEAD()

    def do_POST(self):
        if urlsplit(self.path).path != '/investors/unlock':
            self.send_error(404); return
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            self.send_error(403); return
        try: length = int(self.headers.get('Content-Length', '0'))
        except ValueError: self.send_error(400); return
        if not 0 < length <= 2048:
            self.send_error(400); return
        form = parse_qs(self.rfile.read(length).decode('utf-8', errors='replace'))
        password = form.get('password', [''])[0]
        if not hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), self.server.password_hash):
            self.gate(error=True); return
        now = time.time()
        self.server.sessions = {k: v for k, v in self.server.sessions.items() if v > now}
        token = secrets.token_urlsafe(32)
        self.server.sessions[token] = now + 43200
        self.send_response(303)
        self.send_header('Location', '/investors/')
        self.send_header('Set-Cookie', f'{COOKIE}={token}; Path=/investors; HttpOnly; SameSite=Lax; Max-Age=43200')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def end_headers(self):
        if self.protected():
            self.send_header('Cache-Control', 'private, no-store')
            self.send_header('X-Robots-Tag', 'noindex, noarchive')
            self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def list_directory(self, path):
        self.send_error(403, 'Directory listing is disabled'); return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--port', type=int, default=8790); args = parser.parse_args()
    config = ROOT / '.local/investor-preview.json'
    secret_hash = os.environ.get('REGFIRE_INVESTOR_PASSWORD_HASH', '')
    if not secret_hash and config.exists(): secret_hash = json.loads(config.read_text()).get('password_sha256', '')
    if len(secret_hash) != 64: raise SystemExit('Investor preview password must be configured before starting.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.password_hash = secret_hash; server.sessions = {}; server.serve_forever()
