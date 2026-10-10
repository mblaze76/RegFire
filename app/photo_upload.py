"""Event-scoped private photo collection using expiring, revocable bearer links."""
import hashlib
import io
import json
import re
import secrets
import time
import threading
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from PIL import Image
from access import AccessError
from assets import normalize_image
import photo_screening as screening

ROOT = Path(__file__).resolve().parent
MAX_PHOTO = 5 * 1024 * 1024
_test_lock = threading.Lock()

def digest(token):
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        raise AccessError('This photo link is invalid or has expired. Ask the organizer for a new link.', 404)
    return hashlib.sha256(token.encode()).hexdigest()

def table(store):
    return sql.Identifier(store.schema, 'attendee_photos')

def policy(conn, store, event_id, lock=False):
    row = conn.execute(sql.SQL('SELECT body FROM {} WHERE id=%s' + (' FOR SHARE' if lock else '')).format(store.table()), (event_id,)).fetchone()
    if not row:
        raise AccessError('Event not found.', 404)
    event = row[0]
    if event.get('parent_event_id'):
        return policy(conn, store, event['parent_event_id'], lock)
    return event, screening.validate_settings(event.get('photo_upload', {}))

def active(row):
    if not row or row[3] or row[2] <= datetime.now(timezone.utc):
        raise AccessError('This photo link is invalid or has expired. Ask the organizer for a new link.', 404)

def normalize(content):
    if not content or len(content) > MAX_PHOTO:
        raise ValueError('Choose a JPEG, PNG or WebP image no larger than 5 MB.')
    clean = normalize_image(content)
    with Image.open(io.BytesIO(clean)) as source:
        if min(source.size) < 160:
            raise ValueError('Choose a photo at least 160 pixels wide and tall.')
        source.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        rgb = Image.new('RGB', source.size, 'white')
        if source.mode == 'RGBA':
            rgb.paste(source, mask=source.getchannel('A'))
        else:
            rgb.paste(source.convert('RGB'))
        buffer = io.BytesIO()
        rgb.save(buffer, 'JPEG', quality=88, optimize=True)
        data = buffer.getvalue()
        if len(data) > 1048576:
            raise ValueError('This photo is too detailed. Please choose a smaller photo.')
        return data

def issue(store, event_id, data):
    name, email = data.get('name', ''), data.get('email', '')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 150 or any(ord(c)<32 for c in name):
        raise ValueError('Enter the attendee’s name (up to 150 characters).')
    if not isinstance(email, str) or len(email)>254 or not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+', email):
        raise ValueError('Enter the attendee’s email address to associate their photo.')
    token = secrets.token_urlsafe(32)
    subject = str(uuid.uuid4())
    with store.connect() as conn:
        event, settings = policy(conn, store, event_id, True)
        if event['id'] != event_id:
            raise ValueError('Create photo links from the main event details.')
        if not settings['enabled']:
            raise AccessError('Save Allow photo upload for this event before creating a link.', 409)
        if conn.execute(sql.SQL('SELECT count(*) FROM {} WHERE event_id=%s').format(table(store)), (event_id,)).fetchone()[0] >= 5000:
            raise AccessError('This event has reached its photo-link limit.', 409)
        conn.execute(sql.SQL("INSERT INTO {}(id,event_id,attendee_name,attendee_email,token_hash,expires) VALUES(%s,%s,%s,%s,%s,now()+interval '7 days')").format(table(store)), (subject,event_id,name.strip(),email.strip(),digest(token)))
    return dict(id=subject, path='/photo-upload#token='+token, expires_in_days=7)

def list_subjects(store, event_id):
    with store.connect() as conn:
        rows=conn.execute(sql.SQL('SELECT id,attendee_name,attendee_email,expires,revoked,approved_at,screening FROM {} WHERE event_id=%s ORDER BY created DESC LIMIT 5000').format(table(store)),(event_id,)).fetchall()
    return [dict(id=str(r[0]),name=r[1],email=r[2],expires=r[3].isoformat(),revoked=r[4],approved_at=r[5].isoformat() if r[5] else None,screening=r[6]) for r in rows]

def link_status(store, token):
    with store.connect() as conn:
        row=conn.execute(sql.SQL('SELECT id,event_id,expires,revoked,approved_at FROM {} WHERE token_hash=%s').format(table(store)),(digest(token),)).fetchone()
        active(row)
        event, settings=policy(conn,store,str(row[1]))
    provider=screening.public_status()
    return dict(event_name=event['name'], enabled=settings['enabled'], configured=provider['configured'], approved=bool(row[4]), message=provider['message'], subject_id=str(row[0]))

def upload(store, token, content, transport=None):
    token_hash=digest(token)
    lease=str(uuid.uuid4())
    # Authenticate and enforce the saved event policy before decoding or calling Google.
    with store.connect() as conn:
        row=conn.execute(sql.SQL('SELECT id,event_id,expires,revoked,attempts,attempt_day,lease_until FROM {} WHERE token_hash=%s FOR UPDATE').format(table(store)),(token_hash,)).fetchone()
        active(row)
        event, settings=policy(conn,store,str(row[1]))
        if not settings['enabled']:
            raise AccessError('Photo uploads are disabled for this event.',403)
        now=datetime.now(timezone.utc)
        if row[6] and row[6]>now:
            raise AccessError('A photo is already being checked. Please wait a moment.',409)
        if row[5]==now.date() and row[4]>=10:
            raise AccessError('The daily photo attempt limit was reached. Please try again tomorrow.',429)
        conn.execute(sql.SQL("UPDATE {} SET attempts=CASE WHEN attempt_day=CURRENT_DATE THEN attempts+1 ELSE 1 END,attempt_day=CURRENT_DATE,lease=%s,lease_until=now()+interval '2 minutes' WHERE id=%s").format(table(store)),(lease,row[0]))
    try:
        image=normalize(content)
        result=screening.screen(image,settings,transport)
        with store.connect() as conn:
            # Event lock serializes approval against disabling or changing screening policy.
            _, current=policy(conn,store,str(row[1]),True)
            if current!=settings or not current['enabled']:
                raise AccessError('The event’s photo policy changed. Please reload and try again.',409)
            saved=conn.execute(sql.SQL('UPDATE {} SET photo=%s,screening=%s,approved_at=now(),lease=NULL,lease_until=NULL WHERE id=%s AND token_hash=%s AND lease=%s AND NOT revoked AND expires>now() RETURNING id').format(table(store)),(image,Jsonb(result),row[0],token_hash,lease)).fetchone()
            if not saved:
                raise AccessError('The photo link changed or expired. Please request a new link.',409)
        return dict(status='approved',subject_id=str(row[0]),message='Your photo passed the checks and is saved for this event’s future photo badge.')
    finally:
        with store.connect() as conn:
            conn.execute(sql.SQL('UPDATE {} SET lease=NULL,lease_until=NULL WHERE id=%s AND lease=%s').format(table(store)),(row[0],lease))

def manage(store,event_id,subject,action):
    with store.connect() as conn:
        if action=='revoke':
            row=conn.execute(sql.SQL('UPDATE {} SET revoked=TRUE WHERE id=%s AND event_id=%s RETURNING id').format(table(store)),(subject,event_id)).fetchone()
            if not row:raise AccessError('Photo request not found.',404)
            return dict(ok=True)
        if action=='renew':
            _,settings=policy(conn,store,event_id,True)
            if not settings['enabled']:raise AccessError('Photo uploads are disabled for this event.',403)
            token=secrets.token_urlsafe(32)
            row=conn.execute(sql.SQL("UPDATE {} SET token_hash=%s,expires=now()+interval '7 days',revoked=FALSE,lease=NULL,lease_until=NULL WHERE id=%s AND event_id=%s RETURNING id").format(table(store)),(digest(token),subject,event_id)).fetchone()
            if not row:raise AccessError('Photo request not found.',404)
            return dict(id=subject,path='/photo-upload#token='+token,expires_in_days=7)
        raise ValueError('Choose renew or revoke.')

def json_body(h,limit=4096):
    if not h.headers.get('Content-Type','').startswith('application/json'):raise ValueError('Send JSON.')
    try:size=int(h.headers.get('Content-Length','0'))
    except ValueError:raise ValueError('Invalid request size.')
    if not 0<size<=limit:raise ValueError('Request is missing or too large.')
    body=json.loads(h.rfile.read(size))
    if not isinstance(body,dict):raise ValueError('Send an object.')
    return body

def binary(h,content,mime='image/jpeg'):
    h.send_response(200);h.send_header('Content-Type',mime);h.send_header('Content-Length',str(len(content)));h.send_header('Cache-Control','no-store');h.send_header('X-Content-Type-Options','nosniff');h.send_header('Referrer-Policy','no-referrer');h.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob:; script-src 'self'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'");h.end_headers();h.wfile.write(content)

def handle(h):
    path=urlsplit(h.path).path
    match=re.fullmatch(r'/api/events/([a-f0-9-]{36})/attendee-photos(?:/([a-f0-9-]{36}))?',path)
    files={'/photo-upload':('photo-upload.html','text/html; charset=utf-8'),'/photo-upload.js':('photo-upload.js','text/javascript'),'/photo-upload.css':('photo-upload.css','text/css'),'/photo-settings.js':('photo-settings.js','text/javascript')}
    if not match and path not in (*files,'/api/photo-upload','/api/photo-screening-config','/api/photo-screening-test'):return False
    try:
        store=h.server.store
        if path in files and h.command=='GET':
            name,mime=files[path];binary(h,(ROOT/'static'/name).read_bytes(),mime);return True
        if path=='/api/photo-screening-config':
            from communications import require_owner
            from access_http import access
            require_owner(access(h),h.identity)
            if h.command=='GET':return h.respond(200,screening.public_status()) or True
            if h.command=='POST':return h.respond(200,screening.save_credential(json_body(h))) or True
        if path=='/api/photo-screening-test' and h.command=='POST':
            from communications import require_owner
            from access_http import access
            require_owner(access(h),h.identity)
            data=json_body(h)
            if data.get('confirm_paid_test') is not True:raise ValueError('Confirm sending one synthetic image to Google; usage charges may apply.')
            with _test_lock:
                now=time.monotonic()
                if now-getattr(h.server,'photo_last_test',-60)<60:raise AccessError('Wait a minute before running another Google connection test.',429)
                h.server.photo_last_test=now
            test=io.BytesIO();Image.new('RGB',(160,160),'gray').save(test,'JPEG')
            payload=screening.request(test.getvalue())
            # A gray square has no face. A complete rejection still proves the API responded.
            try:screening.screen(test.getvalue(),dict(enabled=True),lambda _:payload)
            except screening.PhotoRejected:pass
            return h.respond(200,dict(status='connected',message='Google responded successfully to the test just now. The synthetic image is not an approved attendee photo.')) or True
        if match:
            event_id,subject=match.groups()
            if h.command=='GET' and not subject:return h.respond(200,dict(attendees=list_subjects(store,event_id))) or True
            if h.command=='GET' and subject:
                with store.connect() as conn:
                    row=conn.execute(sql.SQL('SELECT photo FROM {} WHERE id=%s AND event_id=%s').format(table(store)),(subject,event_id)).fetchone()
                if not row or row[0] is None:raise AccessError('Approved photo not found.',404)
                binary(h,bytes(row[0]));return True
            if h.command=='POST':
                data=json_body(h)
                return h.respond(200,manage(store,event_id,subject,data.get('action')) if subject else issue(store,event_id,data)) or True
        if path=='/api/photo-upload' and h.command=='POST':
            token=h.headers.get('X-Photo-Token','')
            action=h.headers.get('X-Photo-Action','status')
            if action=='status':return h.respond(200,link_status(store,token)) or True
            if action=='upload':
                if h.headers.get('X-Photo-Consent')!='google-vision':raise ValueError('Confirm permission to send this photo to Google for screening.')
                length=int(h.headers.get('Content-Length','0'))
                if not 0<length<=MAX_PHOTO:raise ValueError('Choose an image no larger than 5 MB.')
                if h.headers.get('Content-Type','').split(';')[0] not in ('image/png','image/jpeg','image/webp'):raise ValueError('Use a JPEG, PNG or WebP image.')
                return h.respond(200,upload(store,token,h.rfile.read(length),getattr(h.server,'photo_transport',None))) or True
        h.respond(405,{'error':'Method not allowed.'})
    except AccessError as exc:h.respond(exc.status,{'error':str(exc)})
    except screening.ScreeningUnavailable as exc:h.respond(503,{'error':str(exc),'status':'unavailable'})
    except (ValueError,UnicodeDecodeError) as exc:h.respond(400,{'error':str(exc),'status':'not_approved'})
    except (psycopg.Error,OSError):h.respond(503,{'error':'Photo storage is unavailable. Please try again; no new photo was approved.'})
    return True
