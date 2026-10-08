"""Opt-in LinkedIn OIDC profile import; no tokens or profiles are persisted.

This is profile autofill, not a RegFire login or membership verification.
"""
import hmac
import json
import os
import re
import secrets
import ssl
import certifi
import threading
import time
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler

AUTHORIZE = 'https://www.linkedin.com/oauth/v2/authorization'
TOKEN = 'https://www.linkedin.com/oauth/v2/accessToken'
USERINFO = 'https://api.linkedin.com/v2/userinfo'
JWKS = 'https://www.linkedin.com/oauth/openid/jwks'
CALLBACK = '/api/linkedin/callback'
TTL = 600


def configuration(origin):
    values = {key: os.environ.get('REGFIRE_LINKEDIN_' + key, '').strip()
              for key in ('CLIENT_ID', 'CLIENT_SECRET', 'REDIRECT_URI')}
    redirect = urlsplit(values['REDIRECT_URI'])
    if (not all(values.values()) or values['REDIRECT_URI'] != origin + CALLBACK
            or redirect.query or redirect.fragment):
        return None
    return values


class Transactions:
    def __init__(self, clock=time.monotonic):
        self.clock, self.items, self.lock = clock, {}, threading.Lock()

    def start(self, flow, request_id, origin, client_id):
        with self.lock:
            now = self.clock()
            self.items = {k: v for k, v in self.items.items() if v['expires'] > now}
            if len(self.items) >= 512:
                raise ValueError('LinkedIn is busy. Please try again shortly.')
            state, binding, nonce = (secrets.token_urlsafe(32) for _ in range(3))
            self.items[state] = dict(flow=flow, request_id=request_id, origin=origin,
                                     client_id=client_id, binding=binding, nonce=nonce,
                                     expires=now + TTL)
            return state, binding, nonce

    def consume(self, state, binding):
        with self.lock:
            value = self.items.get(state)
            if (not value or value['expires'] <= self.clock() or not binding
                    or not hmac.compare_digest(value['binding'], binding)):
                raise ValueError('This LinkedIn request expired. Close this window and try again.')
            return self.items.pop(state)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch_json(url, data=None, token=None):
    headers = {'Accept': 'application/json'}
    if data is not None:
        data = urlencode(data).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with build_opener(NoRedirects, HTTPSHandler(context=ssl.create_default_context(cafile=certifi.where()))).open(Request(url, data=data, headers=headers), timeout=10) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError('Invalid LinkedIn response.')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('Invalid LinkedIn response.')
    return result


def validate_token(token, client_id, nonce):
    import jwt
    key = jwt.PyJWKClient(JWKS, timeout=10, ssl_context=ssl.create_default_context(cafile=certifi.where())).get_signing_key_from_jwt(token).key
    claims = jwt.decode(token, key, algorithms=['RS256'], audience=client_id,
                        issuer='https://www.linkedin.com',
                        options={'require': ['exp', 'iat', 'sub', 'aud', 'iss', 'nonce']})
    if not isinstance(claims.get('nonce'), str) or not hmac.compare_digest(claims['nonce'], nonce):
        raise ValueError('LinkedIn response did not match this request.')
    if claims.get('azp', client_id) != client_id:
        raise ValueError('Invalid LinkedIn audience.')
    return claims


def profile_from_code(code, transaction, config):
    if not isinstance(code, str) or not 1 <= len(code) <= 4096:
        raise ValueError('Missing LinkedIn authorization.')
    tokens = fetch_json(TOKEN, dict(grant_type='authorization_code', code=code,
                                    redirect_uri=config['REDIRECT_URI'],
                                    client_id=config['CLIENT_ID'], client_secret=config['CLIENT_SECRET']))
    access_token, id_token = tokens.get('access_token'), tokens.get('id_token')
    if not isinstance(access_token, str) or not isinstance(id_token, str):
        raise ValueError('LinkedIn did not return the required permissions.')
    claims = validate_token(id_token, config['CLIENT_ID'], transaction['nonce'])
    info = fetch_json(USERINFO, token=access_token)
    if not isinstance(info.get('sub'), str) or info['sub'] != claims['sub']:
        raise ValueError('LinkedIn profile did not match this request.')
    profile = {}
    for key in ('given_name', 'family_name', 'email'):
        value = info.get(key)
        if isinstance(value, str) and 0 < len(value.strip()) <= 254:
            if key != 'email' or re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value.strip()):
                profile[key] = value.strip()
    return profile


_lock = threading.Lock()


def transactions(server):
    with _lock:
        if not hasattr(server, 'linkedin_transactions'):
            server.linkedin_transactions = Transactions()
        return server.linkedin_transactions


def cookie_name(state):
    return 'regfire_linkedin_' + state[:20]


def popup(h, message, payload=None, origin=None, cookie=None):
    nonce = secrets.token_urlsafe(20)
    safe = lambda value: json.dumps(value).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    script = 'document.getElementById("message").textContent=' + safe(message) + ';'
    if payload and origin:
        script += 'if(window.opener){window.opener.postMessage(' + safe(payload) + ',' + safe(origin) + ');window.close();}'
    content = ('<!doctype html><meta charset="utf-8"><title>LinkedIn profile import</title>'
               '<h1>LinkedIn profile import</h1><p id="message"></p><p>You may close this window.</p>'
               '<script nonce="' + nonce + '">' + script + '</script>').encode()
    h.send_response(200)
    for name, value in [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(content))),
                        ('Cache-Control', 'no-store'), ('Referrer-Policy', 'no-referrer'),
                        ('X-Frame-Options', 'DENY'), ('X-Content-Type-Options', 'nosniff'),
                        ('Content-Security-Policy', "default-src 'none'; script-src 'nonce-" + nonce + "'; frame-ancestors 'none'; base-uri 'none'")]:
        h.send_header(name, value)
    if cookie:
        h.send_header('Set-Cookie', cookie + '=; HttpOnly; SameSite=Lax; Path=/api/linkedin; Max-Age=0')
    h.end_headers()
    h.wfile.write(content)


def handle(h):
    path = urlsplit(h.path).path
    if path not in ('/api/linkedin/status', '/api/linkedin/start', CALLBACK):
        return False
    if h.command != 'GET':
        h.respond(405, {'error': 'Method not allowed.'})
        return True
    origin = 'http://' + h.headers['Host']  # Host already constrained by the local server.
    config = configuration(origin)
    if path == '/api/linkedin/status':
        h.respond(200, {'available': bool(config)})
        return True
    query = parse_qs(urlsplit(h.path).query)
    one = lambda key: query.get(key, [''])[0] if len(query.get(key, [])) <= 1 else ''
    if path == '/api/linkedin/start':
        if not config:
            popup(h, 'LinkedIn is not connected for this event. Please fill in your details manually.')
            return True
        from access_http import access
        from access import AccessError
        try:
            flow, request_id = one('flow'), one('request')
            if not re.fullmatch(r'[a-f0-9-]{36}', flow) or not re.fullmatch(r'[a-f0-9-]{36}', request_id):
                raise ValueError('Open LinkedIn from the registration form.')
            access(h).require_event(h.identity, flow)
            state, binding, nonce = transactions(h.server).start(flow, request_id, origin, config['CLIENT_ID'])
            url = AUTHORIZE + '?' + urlencode(dict(response_type='code', client_id=config['CLIENT_ID'],
                          redirect_uri=config['REDIRECT_URI'], scope='openid profile email', state=state, nonce=nonce))
            h.send_response(303)
            h.send_header('Location', url)
            h.send_header('Cache-Control', 'no-store')
            h.send_header('Referrer-Policy', 'no-referrer')
            h.send_header('Set-Cookie', cookie_name(state) + '=' + binding + '; HttpOnly; SameSite=Lax; Path=/api/linkedin; Max-Age=' + str(TTL))
            h.end_headers()
        except (ValueError, AccessError) as error:
            popup(h, str(error))
        return True
    transaction = None
    state = one('state')
    cookie = cookie_name(state) if re.fullmatch(r'[A-Za-z0-9_-]{43}', state) else None
    try:
        cookies = SimpleCookie()
        cookies.load(h.headers.get('Cookie', ''))
        binding = cookies[cookie].value if cookie in cookies else ''
        transaction = transactions(h.server).consume(state, binding)
        if not config or transaction['origin'] != origin or transaction['client_id'] != config['CLIENT_ID']:
            raise ValueError('LinkedIn settings changed. Please try again.')
        if one('error'):
            message, profile = 'LinkedIn import was canceled. Your entries are unchanged.', None
        else:
            profile = profile_from_code(one('code'), transaction, config)
            message = 'Your LinkedIn details are ready for the registration form.'
    except Exception:
        message, profile = 'LinkedIn import could not be completed. Your entries are unchanged; please try again or enter them manually.', None
    payload = dict(type='regfire-linkedin-profile', request=transaction['request_id'], flow=transaction['flow'],
                   profile=profile, message=message) if transaction else None
    popup(h, message, payload, transaction['origin'] if transaction else None, cookie)
    return True
