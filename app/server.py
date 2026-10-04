#!/usr/bin/env python3
"""Local Regfire draft workspace. PostgreSQL edition."""
import argparse, json, uuid, re
import psycopg
from database import Store
from registration import validate_page
from assets import MAX_UPLOAD
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
FIELDS = ('name', 'start', 'end', 'timezone', 'format', 'venue', 'location', 'url', 'description', 'organizer', 'email')

def validate(data):
    if not isinstance(data, dict): raise ValueError('An event object is required.')
    result = {}
    for key in FIELDS:
        value = data.get(key, '')
        if not isinstance(value, str): raise ValueError(f'{key} must be text.')
        result[key] = value.strip()
        if len(result[key]) > (10000 if key == 'description' else 500): raise ValueError(f'{key} is too long.')
    address=data.get('address',{})
    if not isinstance(address,dict):raise ValueError('Address details must be an object.')
    result['address']={}
    for key in ('line1','line2','city','region','postal','country'):
        value=address.get(key,'')
        if not isinstance(value,str) or len(value)>500:raise ValueError('Address fields must be text of at most 500 characters.')
        result['address'][key]=value.strip()
    if not result['name']: raise ValueError('Give your event a name.')
    if result['format'] not in ('in_person', 'online'): raise ValueError('Choose an event format.')
    try: zone = ZoneInfo(result['timezone'])
    except Exception: raise ValueError('Choose a valid timezone.')
    dates = {}
    for key in ('start', 'end'):
        if result[key]:
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', result[key]): raise ValueError()
                date = datetime.fromisoformat(result[key])
                aware = date.replace(tzinfo=zone)
                if aware.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != date: raise ValueError()
                dates[key] = aware.astimezone(timezone.utc)
            except ValueError: raise ValueError(f'Enter a valid {key} date and time in this timezone.')
    if 'end' in dates and 'start' not in dates: raise ValueError('Add a start time before an end time.')
    if len(dates) == 2 and dates['end'] <= dates['start']: raise ValueError('End time must be after start time.')
    if result['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', result['email']): raise ValueError('Enter a valid organizer email.')
    if result['url']:
        url = urlsplit(result['url'])
        if url.scheme not in ('https', 'http') or not url.hostname: raise ValueError('Use a complete http or https event link.')
    return result

class Handler(BaseHTTPRequestHandler):
    def parse_request(self):
        if not super().parse_request():return False
        if self.headers.get('Host') not in ('127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)):
            self.send_error(403,'Use the local Regfire address.');return False
        from access_http import guard
        return guard(self)

    def respond(self, status, value):
        content = json.dumps(value).encode()
        self.send_response(status); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(content))); self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(content)
    def do_GET(self):
        from access_http import handle
        if handle(self):return
        path = urlsplit(self.path).path
        if path.endswith('/event-footer'): return self.footer_request(False)
        if re.fullmatch(r'/api/events/[a-f0-9-]{36}/sessions',path): return self.sessions_request('get')
        if path=='/api/registrant-event':
            try:
                event_id=str(uuid.UUID(parse_qs(urlsplit(self.path).query).get('event',[''])[0]))
                with self.server.store.connect() as conn:
                    row=conn.execute(psycopg.sql.SQL("SELECT 1 FROM {} WHERE id=%s AND NOT (body ? 'parent_event_id')").format(self.server.store.table()),(event_id,)).fetchone()
                return self.respond(200,{'event_id':event_id}) if row else self.respond(404,{'error':'Event not found.'})
            except ValueError:return self.respond(400,{'error':'Invalid event reference.'})
            except psycopg.Error:return self.respond(503,{'error':'Could not verify this event.'})
        model_match=re.fullmatch(r'/api/events/([a-f0-9-]{36})/flow-preview',path)
        if model_match:
            try:
                event_id=str(uuid.UUID(model_match[1]))
                with self.server.store.connect() as conn:
                    row=conn.execute(psycopg.sql.SQL('SELECT e.body FROM {} e JOIN {} f ON f.id=e.id WHERE e.id=%s AND NOT f.archived').format(self.server.store.table(),psycopg.sql.Identifier(self.server.store.schema,'registration_flows')),(event_id,)).fetchone()
                if not row:return self.respond(404,{'error':'Flow not found.'})
                return self.respond(200,dict(event=row[0],registration=self.server.store.registration_page(event_id),demographics=self.server.store.demographics_page(event_id),at='',regtype=None))
            except psycopg.Error:return self.respond(503,{'error':'Could not load flow preview.'})
        if path.endswith('/flows'): return self.flows_request(False)
        if path.endswith('/welcome-page'): return self.welcome_request(False)
        if re.fullmatch(r'/api/events/[a-f0-9-]{36}/membership',path):return self.membership_request('get')
        asset_match=re.fullmatch(r'/api/events/([a-f0-9-]{36})/assets/([a-f0-9-]{36})',path)
        if asset_match:
            try:
                event_id,asset_id=[str(uuid.UUID(value)) for value in asset_match.groups()]
                asset=self.server.store.asset(event_id,asset_id)
                if not asset or not re.fullmatch(r'[a-f0-9-]{36}\.png',asset[0]):return self.respond(404,{'error':'Image not found.'})
                content=(getattr(self.server,'upload_root',ROOT/'uploads')/asset[0]).read_bytes()
                self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','private, max-age=3600');self.end_headers();self.wfile.write(content);return
            except (ValueError,FileNotFoundError):return self.respond(404,{'error':'Image not found.'})
            except (psycopg.Error,OSError):return self.respond(503,{'error':'Image unavailable.'})
        if path == '/api/address-config':
            from address_lookup import config
            return self.respond(200,config())
        if path == '/api/events':
            try:
                from access_http import access
                return self.respond(200, access(self).event_list(self.identity))
            except psycopg.Error: return self.respond(503, {'error': 'Drafts could not be loaded. Check the local database and retry.'})
        match = re.fullmatch(r'/api/events/([a-f0-9-]{36})/registration-page', path)
        if match:
            try:
                event_id = str(uuid.UUID(match[1]))
                page = self.server.store.registration_page(event_id)
                return self.respond(200, page) if page else self.respond(404, {'error': 'Event not found.'})
            except ValueError: return self.respond(400, {'error': 'Invalid event ID.'})
            except psycopg.Error: return self.respond(503, {'error': 'Could not load the registration page. Please retry.'})
        demographic=re.fullmatch(r'/api/events/([a-f0-9-]{36})/demographics',path)
        if demographic:
            try:
                result=self.server.store.demographics_page(str(uuid.UUID(demographic[1])))
                return self.respond(200,result) if result else self.respond(404,{'error':'Event not found.'})
            except ValueError:return self.respond(400,{'error':'Invalid event ID.'})
            except psycopg.Error:return self.respond(503,{'error':'Could not load demographics.'})
        if path == '/api/timezones': return self.respond(200, sorted(available_timezones()))
        files = {'/membership': ('membership.html','text/html'), '/membership-site.js': ('membership-site.js','text/javascript'), '/spark-position.js': ('spark-position.js','text/javascript'), '/spark-3d.png': ('spark-3d.png','image/png'), '/spark-turns.png': ('spark-turns.png','image/png'), '/color-control.js': ('color-control.js','text/javascript'), '/event-footer.js': ('event-footer.js','text/javascript'), '/spark.svg': ('spark.svg','image/svg+xml'), '/spark.css': ('spark.css','text/css'), '/spark.js': ('spark.js','text/javascript'), '/sessions': ('sessions.html','text/html'), '/sessions.css': ('sessions.css','text/css'), '/sessions-common.js': ('sessions-common.js','text/javascript'), '/sessions-builder.js': ('sessions-builder.js','text/javascript'), '/sessions-site.js': ('sessions-site.js','text/javascript'), '/welcome-fonts.js': ('welcome-fonts.js','text/javascript'), '/regfire-logo-3d-transparent.png': ('regfire-logo-3d-transparent.png','image/png'), '/login': ('login.html','text/html'), '/admin': ('admin.html','text/html'), '/products': ('products.html','text/html'), '/access.css': ('access.css','text/css'), '/access-ui.js': ('access-ui.js','text/javascript'), '/auth-client.js': ('auth-client.js','text/javascript'), '/': ('index.html', 'text/html'), '/autosave.js': ('autosave.js', 'text/javascript'), '/app.js': ('app.js', 'text/javascript'), '/welcome.js': ('welcome.js', 'text/javascript'), '/welcome-common.js': ('welcome-common.js','text/javascript'), '/welcome-heading.js': ('welcome-heading.js','text/javascript'), '/flows.js': ('flows.js','text/javascript'), '/welcome-site.js': ('welcome-site.js','text/javascript'), '/registrant-login': ('registrant-login.html','text/html'), '/registrant-login.js': ('registrant-login.js','text/javascript'), '/welcome': ('welcome.html','text/html'), '/builder.js': ('builder.js', 'text/javascript'), '/demographics.js': ('demographics.js', 'text/javascript'), '/membership.js': ('membership.js', 'text/javascript'), '/address.js': ('address.js', 'text/javascript'), '/footer.js': ('footer.js', 'text/javascript'), '/email.js': ('email.js', 'text/javascript'), '/live-editor.js': ('live-editor.js', 'text/javascript'), '/live-preview.js': ('live-preview.js', 'text/javascript'), '/preview': ('preview.html', 'text/html'), '/style.css': ('style.css', 'text/css'), '/regfire-logo.png': ('regfire-logo.png', 'image/png')}
        if path not in files: return self.respond(404, {'error': 'Not found'})
        filename, content_type = files[path]; content = (ROOT / 'static' / filename).read_bytes()
        self.send_response(200); self.send_header('Content-Type', content_type + '; charset=utf-8'); self.send_header('Content-Length', str(len(content))); self.send_header('X-Content-Type-Options', 'nosniff'); self.send_header('Cache-Control','no-store'); self.send_header('Referrer-Policy','same-origin'); self.send_header('X-Frame-Options','SAMEORIGIN'); self.end_headers(); self.wfile.write(content)
    def do_POST(self):
        if "/sessions/" in urlsplit(self.path).path: return self.sessions_request(urlsplit(self.path).path.rsplit("/",1)[-1])
        if urlsplit(self.path).path.endswith('/flows'):return self.flows_request(True)
        from access_http import handle
        if handle(self):return
        if urlsplit(self.path).path in ('/api/address-suggestions','/api/address-details'):return self.address_request()
        if '/membership/' in urlsplit(self.path).path:return self.membership_request(urlsplit(self.path).path.rsplit('/',1)[-1])
        if urlsplit(self.path).path.endswith('/demographics-preview'):return self.demographics_request(True)
        upload=re.fullmatch(r'/api/events/([a-f0-9-]{36})/assets/(logo|background)',urlsplit(self.path).path)
        if upload:
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+self.headers.get('Host',''):return self.respond(403,{'error':'Cross-origin requests are not allowed.'})
            try:
                event_id=str(uuid.UUID(upload[1]));length=int(self.headers.get('Content-Length',0))
                if not 0<length<=MAX_UPLOAD:raise ValueError('Choose an image no larger than 8 MB.')
                asset=self.server.store.save_asset(event_id,upload[2],self.rfile.read(length),getattr(self.server,'upload_root',None))
                return self.respond(201,asset) if asset else self.respond(404,{'error':'Event not found.'})
            except ValueError as exc:return self.respond(400,{'error':str(exc)})
            except (psycopg.Error,OSError):return self.respond(503,{'error':'Could not store the image. Your saved page is unchanged.'})
        match = re.fullmatch(r'/api/events/([a-f0-9-]{36})/pricing-preview', urlsplit(self.path).path)
        if not match:
            if urlsplit(self.path).path!='/api/events':return self.respond(404,{'error':'Not found.'})
            return self.save(False)
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.respond(403, {'error': 'Cross-origin requests are not allowed.'})
        try:
            event_id = str(uuid.UUID(match[1]))
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 500000: raise ValueError('Preview data is missing or too large.')
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict): raise ValueError('A preview object is required.')
            at=body.get('at','')
            if not isinstance(at,str): raise ValueError('Preview time must be text.')
            result=self.server.store.preview_registration_pricing(event_id,body.get('page'),at)
            return self.respond(200,result) if result else self.respond(404,{'error':'Event not found.'})
        except (ValueError, UnicodeDecodeError) as exc: return self.respond(400,{'error':str(exc)})
        except psycopg.Error: return self.respond(503,{'error':'Could not evaluate pricing. Please retry.'})
    def do_PUT(self):
        if urlsplit(self.path).path.endswith("/event-footer"): return self.footer_request(True)
        if urlsplit(self.path).path.endswith("/sessions"): return self.sessions_request("save")
        if urlsplit(self.path).path.endswith('/welcome-page'):return self.welcome_request(True)
        if urlsplit(self.path).path.endswith('/membership'):return self.membership_request('save')
        if urlsplit(self.path).path.endswith('/demographics'):return self.demographics_request(False)
        match = re.fullmatch(r'/api/events/([a-f0-9-]{36})/registration-page', urlsplit(self.path).path)
        if not match: return self.save(True)
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.respond(403, {'error': 'Cross-origin requests are not allowed.'})
        try:
            event_id = str(uuid.UUID(match[1]))
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 500000: raise ValueError('Page data is missing or too large (500 KB maximum).')
            data = json.loads(self.rfile.read(length))
            saved = self.server.store.save_registration_page(event_id, data, datetime.now(timezone.utc).isoformat())
            return self.respond(200, saved) if saved else self.respond(404, {'error': 'Event not found.'})
        except (ValueError, UnicodeDecodeError) as exc: return self.respond(400, {'error': str(exc)})
        except psycopg.Error: return self.respond(503, {'error': 'Could not save the registration page. Your changes are still here; please retry.'})
    def footer_request(self, save):
        match=re.fullmatch(r'/api/events/([a-f0-9-]{36})/event-footer',urlsplit(self.path).path)
        if not match:return self.respond(404,{'error':'Not found.'})
        try:
            data=None
            if save:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=20000:raise ValueError('Footer is missing or too large.')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('Send a footer object.')
            from event_footer import operation
            result=operation(self.server.store,str(uuid.UUID(match[1])),data)
            return self.respond(200,result) if result is not None else self.respond(404,{'error':'Event not found.'})
        except (ValueError,UnicodeDecodeError) as exc:return self.respond(400,{'error':str(exc)})
        except psycopg.Error:return self.respond(503,{'error':'Could not access the shared footer. Keep your edits and retry.'})

    def sessions_request(self, action):
        suffix = '/'+action if action in ('import-preview','import') else ''
        match = re.fullmatch(r'/api/events/([a-f0-9-]{36})/sessions'+suffix, urlsplit(self.path).path)
        if not match or action not in ('get','save','import-preview','import'): return self.respond(404,{'error':'Not found.'})
        try:
            data=None
            if action!='get':
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=3_000_000: raise ValueError('Sessions data is missing or too large.')
                data=json.loads(self.rfile.read(length))
            from sessions import operation
            result=operation(self.server.store,str(uuid.UUID(match[1])),action,data)
            return self.respond(200,result) if result is not None else self.respond(404,{'error':'Event not found.'})
        except (ValueError,UnicodeDecodeError) as exc: return self.respond(400,{'error':str(exc)})
        except psycopg.Error: return self.respond(503,{'error':'Sessions could not be loaded or saved. Keep your edits and retry.'})

    def flows_request(self, save):
        match=re.fullmatch(r'/api/events/([a-f0-9-]{36})/flows',urlsplit(self.path).path)
        if not match:return self.respond(404,{'error':'Not found.'})
        try:
            data=None
            if save:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=100000:raise ValueError('Flow data is missing or too large.')
                data=json.loads(self.rfile.read(length))
            flows=self.server.store.flows(str(uuid.UUID(match[1])),data,datetime.now(timezone.utc).isoformat())
            return self.respond(200,flows) if flows is not None else self.respond(404,{'error':'Event not found.'})
        except (ValueError,UnicodeDecodeError) as exc:return self.respond(400,{'error':str(exc)})
        except psycopg.Error:return self.respond(503,{'error':'Could not save registration flows.'})

    def welcome_request(self, save):
        match=re.fullmatch(r'/api/events/([a-f0-9-]{36})/welcome-page',urlsplit(self.path).path)
        if not match:return self.respond(404,{'error':'Not found.'})
        origin=self.headers.get('Origin')
        if save and origin and origin!='http://'+self.headers.get('Host',''):return self.respond(403,{'error':'Cross-origin requests are not allowed.'})
        try:
            data=None
            if save:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=100000:raise ValueError('Welcome page data is missing or too large.')
                data=json.loads(self.rfile.read(length))
            page=self.server.store.welcome_page(str(uuid.UUID(match[1])),data,datetime.now(timezone.utc).isoformat())
            return self.respond(200,page) if page else self.respond(404,{'error':'Event not found.'})
        except (ValueError,UnicodeDecodeError) as exc:return self.respond(400,{'error':str(exc)})
        except psycopg.Error:return self.respond(503,{'error':'Could not access the welcome page. Your edits are still here; retry saving.'})

    def address_request(self):
        origin=self.headers.get('Origin')
        if origin and origin!='http://'+self.headers.get('Host',''):return self.respond(403,{'error':'Cross-origin requests are not allowed.'})
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=2000:raise ValueError('Address query is missing or too large.')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError('Invalid address query.')
            from address_lookup import suggestions
            if urlsplit(self.path).path=='/api/address-details':
                from google_addresses import details
                from membership import Unavailable
                try:return self.respond(200,details(data.get('place_id'),data.get('session')))
                except Unavailable:return self.respond(503,{'error':'Google address details are unavailable. Enter the address manually.'})
            return self.respond(200,suggestions(data.get('query'),session=data.get('session')))
        except (ValueError,UnicodeDecodeError) as exc:return self.respond(400,{'error':str(exc)})

    def do_DELETE(self):
        match=re.fullmatch(r'/api/events/([a-f0-9-]{36})',urlsplit(self.path).path)
        if not match:return self.respond(404,{'error':'Not found.'})
        origin=self.headers.get('Origin')
        if origin and origin!='http://'+self.headers.get('Host',''):return self.respond(403,{'error':'Cross-origin requests are not allowed.'})
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=2000:raise ValueError('A named event confirmation is required.')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict) or not isinstance(data.get('confirm_name'),str):raise ValueError('Confirm the selected event name.')
            result=self.server.store.delete_event(str(uuid.UUID(match[1])),data['confirm_name'],getattr(self.server,'upload_root',None))
            return self.respond(200,result) if result else self.respond(404,{'error':'This event no longer exists.'})
        except (ValueError,UnicodeDecodeError) as exc:return self.respond(400,{'error':str(exc)})
        except psycopg.Error:return self.respond(503,{'error':'The event could not be deleted. Reload and retry.'})

    def membership_request(self,action):
        suffix='' if action in ('get','save') else '/'+action
        match=re.fullmatch(r'/api/events/([a-f0-9-]{36})/membership'+suffix,urlsplit(self.path).path)
        if not match or action not in ('get','save','import-preview','import','lookup','test'):return self.respond(404,{'error':'Not found.'})
        origin=self.headers.get('Origin')
        if origin and origin!='http://'+self.headers.get('Host',''):return self.respond(403,{'error':'Cross-origin requests are not allowed.'})
        try:
            data={}
            if action!='get':
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<=2500000:raise ValueError('Membership request is missing or too large.')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('Membership request must be an object.')
            result=self.server.store.membership(str(uuid.UUID(match[1])),action,data)
            return self.respond(200,result) if result is not None else self.respond(404,{'error':'Event not found.'})
        except (ValueError,UnicodeDecodeError) as exc:return self.respond(400,{'error':str(exc)})
        except psycopg.Error:return self.respond(503,{'error':'Membership settings are unavailable. Please retry.'})

    def demographics_request(self,preview):
        match=re.fullmatch(r'/api/events/([a-f0-9-]{36})/'+('demographics-preview' if preview else 'demographics'),urlsplit(self.path).path)
        if not match:return self.respond(404,{'error':'Not found.'})
        origin=self.headers.get('Origin')
        if origin and origin!='http://'+self.headers.get('Host',''):return self.respond(403,{'error':'Cross-origin requests are not allowed.'})
        try:
            event_id=str(uuid.UUID(match[1]));length=int(self.headers.get('Content-Length',0))
            if not 0<length<=500000:raise ValueError('Demographics data is missing or exceeds 500 KB.')
            data=json.loads(self.rfile.read(length))
            if preview:
                if not isinstance(data,dict) or not isinstance(data.get('answers',{}),dict) or type(data.get('check',False)) is not bool:raise ValueError('Invalid preview request.')
                result=self.server.store.demographics_operation(event_id,data.get('page'),data.get('answers',{}),data.get('regtype_id'),data.get('check',False),data.get('registration_page'))
            else:result=self.server.store.demographics_operation(event_id,data)
            return self.respond(200,result) if result is not None else self.respond(404,{'error':'Event not found.'})
        except (ValueError,UnicodeDecodeError) as exc:return self.respond(400,{'error':str(exc)})
        except psycopg.Error:return self.respond(503,{'error':'Demographics could not be saved or previewed. Please retry.'})

    def save(self, editing):
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''): return self.respond(403, {'error': 'Cross-origin requests are not allowed.'})
        path = urlsplit(self.path).path
        if (not editing and path != '/api/events') or (editing and not re.fullmatch(r'/api/events/[a-f0-9-]{36}', path)): return self.respond(404, {'error': 'Not found'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 50000: raise ValueError('Event data is missing or too large.')
            data = validate(json.loads(self.rfile.read(length)))
            now = datetime.now(timezone.utc).isoformat()
            event_id = path.rsplit('/', 1)[-1] if editing else str(uuid.uuid4())
            data = self.server.store.save(event_id, data, now, editing, creator_id=self.identity['id'] if not editing else None)
            if data is None: return self.respond(404, {'error': 'This draft no longer exists.'})
            self.respond(200 if editing else 201, data)
        except (ValueError, UnicodeDecodeError) as exc: self.respond(400, {'error': str(exc)})
        except psycopg.Error: self.respond(503, {'error': 'Could not save. Your form is still here; check database access and try again.'})

def main():
    import os
    from google_addresses import key
    if key():os.environ.setdefault("REGFIRE_ADDRESS_PROVIDER","google")
    parser = argparse.ArgumentParser(); parser.add_argument('--port', type=int, default=8765); args = parser.parse_args()
    try:
        store = Store(); store.initialize()
    except RuntimeError as exc:
        raise SystemExit('RegFire configuration: '+str(exc)+' Existing data is unchanged.')
    except psycopg.Error as exc:
        detail=str(exc).lower()
        if 'operation not permitted' in detail or 'permission denied' in detail:
            reason='The launch environment blocked database access. Allow local network access for this session, or launch with start-regfire.command in Terminal.'
        elif 'connection refused' in detail:
            reason='PostgreSQL is not accepting connections at the configured address. Check the existing PostgreSQL service, then retry.'
        elif 'password authentication failed' in detail:
            reason='PostgreSQL rejected the configured credentials. Check the private local connection settings.'
        else:
            reason='The configured PostgreSQL connection failed. Check service availability and private local connection settings.'
        raise SystemExit(reason+' No database setup or data reset was performed.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler); server.store = store
    from access import Access
    import owner_setup
    server.access=Access(store);owner_setup.prepare(server.access)
    print(f'Regfire is running at http://127.0.0.1:{args.port}', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__ == '__main__': main()
