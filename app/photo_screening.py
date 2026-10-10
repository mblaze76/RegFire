"""Server-only Google Vision screening. No image is approved after an incomplete scan."""
import base64
import http.client
import json
import os
import stat
import time
from pathlib import Path
from membership import PinnedHTTPS, public_addresses, Unavailable

KEY_FILE = Path(__file__).resolve().parent / '.local/google-vision-key'
LEVELS = ('VERY_UNLIKELY', 'UNLIKELY', 'POSSIBLE', 'LIKELY', 'VERY_LIKELY')

class ScreeningUnavailable(Exception):
    pass

class PhotoRejected(ValueError):
    pass

def validate_settings(value):
    if not isinstance(value, dict):
        raise ValueError('Photo upload settings must be an object.')
    result = {}
    for name, default in [('enabled', False), ('safe_search', True), ('face_check', True)]:
        result[name] = value.get(name, default)
        if type(result[name]) is not bool:
            raise ValueError('Photo upload options must be on or off.')
    result['threshold'] = value.get('threshold', 'LIKELY')
    if result['threshold'] not in ('POSSIBLE', 'LIKELY'):
        raise ValueError('Choose a supported photo screening sensitivity.')
    if result['enabled'] and not (result['safe_search'] and result['face_check']):
        raise ValueError('Enable both content screening and the face check before allowing photo uploads.')
    return result

def credential():
    value = os.environ.get('REGFIRE_GOOGLE_VISION_API_KEY', '')
    if not value and KEY_FILE.exists():
        if KEY_FILE.is_symlink() or stat.S_IMODE(KEY_FILE.stat().st_mode) & 0o077:
            raise ScreeningUnavailable('The photo-screening credential file needs private permissions.')
        try:
            value = KEY_FILE.read_text().strip()
        except OSError:
            raise ScreeningUnavailable('Photo-screening credentials are unavailable.') from None
    if value and (len(value) > 512 or any(not (c.isascii() and (c.isalnum() or c in '_-')) for c in value)):
        raise ScreeningUnavailable('Photo-screening credentials are invalid.')
    return value

def public_status():
    try:
        configured = bool(credential())
        return dict(revision=revision(), environment_managed=bool(os.environ.get('REGFIRE_GOOGLE_VISION_API_KEY')), provider='google_vision', configured=configured, credential='••••••••' if configured else '', status='configured' if configured else 'unconfigured', live_verified=False,
                    message='Google Cloud Vision credential configured; live connection not verified.' if configured else 'Google Cloud Vision is not configured. Photo uploads cannot be approved until a server credential is configured.')
    except ScreeningUnavailable as exc:
        return dict(provider='google_vision', configured=False, credential='', status='error', live_verified=False, message=str(exc))

def request(content):
    key = credential()
    if not key:
        raise ScreeningUnavailable('Photo screening is not configured. Please contact the event organizer.')
    body = json.dumps({'requests': [{'image': {'content': base64.b64encode(content).decode('ascii')}, 'features': [{'type': 'SAFE_SEARCH_DETECTION'}, {'type': 'FACE_DETECTION', 'maxResults': 10}]}]})
    conn = None
    try:
        host = 'vision.googleapis.com'
        conn = PinnedHTTPS(host, public_addresses(host)[0])
        conn.request('POST', '/v1/images:annotate', body=body, headers={'X-Goog-Api-Key': key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        response = conn.getresponse()
        data = b''
        deadline = time.monotonic() + 10
        while len(data) <= 131072:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ScreeningUnavailable('Photo screening timed out. Please try again.')
            if conn.sock:
                conn.sock.settimeout(min(5, remaining))
            chunk = response.read1(min(8192, 131073-len(data)))
            if not chunk:
                break
            data += chunk
        if response.status != 200 or len(data) > 131072:
            raise ScreeningUnavailable('Photo screening is unavailable. Please try again or contact the organizer.')
        return json.loads(data)
    except (OSError, ValueError, http.client.HTTPException, Unavailable):
        raise ScreeningUnavailable('Photo screening is unavailable. Please try again.') from None
    finally:
        if conn:
            conn.close()

def screen(content, settings, transport=None):
    policy = validate_settings(settings)
    if not policy['enabled']:
        raise PhotoRejected('Photo uploads are disabled for this event.')
    try:
        payload = (transport or request)(content)
        rows = payload['responses']
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict) or rows[0].get('error'):
            raise ValueError()
        result = rows[0]
        safe = result['safeSearchAnnotation']
        if not isinstance(safe, dict) or any(safe.get(k) not in LEVELS for k in ('adult', 'violence', 'racy')):
            raise ValueError()
        if any(LEVELS.index(safe[k]) >= LEVELS.index(policy['threshold']) for k in ('adult', 'violence', 'racy')):
            raise PhotoRejected('This photo did not pass the content check. Please choose a different photo.')
        faces = result.get('faceAnnotations', [])
        if not isinstance(faces, list) or any(not isinstance(f, dict) or type(f.get('detectionConfidence')) not in (int, float) or not 0 <= f['detectionConfidence'] <= 1 for f in faces):
            raise ValueError()
        if len(faces) != 1 or faces[0]['detectionConfidence'] < 0.8:
            raise PhotoRejected('Please use a clear photo showing only your face, looking toward the camera.')
        return {'status': 'approved', 'provider': 'google_vision', 'content_check': 'passed', 'face_check': 'passed', 'policy': policy}
    except PhotoRejected:
        raise
    except (KeyError, IndexError, TypeError, ValueError):
        raise ScreeningUnavailable('The photo check was incomplete. Please try again; this photo has not been approved.') from None

def save_credential(data):
    """Owner-only caller; atomically replace private local credentials, never return them."""
    import fcntl
    import tempfile
    from access import AccessError
    if os.environ.get('REGFIRE_GOOGLE_VISION_API_KEY'):
        raise AccessError('This server uses an environment credential. Update it on the server instead.', 409)
    action=data.get('action')
    if action not in ('replace','clear'):
        raise ValueError('Choose replace or clear for the server credential.')
    value=data.get('secret','') if action=='replace' else ''
    if action=='replace' and (not isinstance(value,str) or not 16<=len(value)<=512 or any(not (c.isascii() and (c.isalnum() or c in '_-')) for c in value)):
        raise ValueError('Enter a valid Google Cloud API key in the private credential field.')
    KEY_FILE.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if KEY_FILE.parent.is_symlink() or stat.S_IMODE(KEY_FILE.parent.stat().st_mode)&0o077:
        raise ScreeningUnavailable('The credential directory requires private server permissions.')
    with os.fdopen(os.open(KEY_FILE.with_suffix('.lock'),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600),'w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if data.get('revision')!=revision():
            raise AccessError('Photo credentials changed. Reload this section before saving.',409)
        credential()  # Do not overwrite a symlink or an insecure existing file.
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(mode='w',dir=KEY_FILE.parent,prefix='.vision-',delete=False) as stream:
                temporary=Path(stream.name);os.chmod(temporary,0o600);stream.write(value);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,KEY_FILE)
        finally:
            if temporary and temporary.exists():temporary.unlink()
    return public_status()

def revision():
    return str(KEY_FILE.stat().st_mtime_ns) if KEY_FILE.exists() else 'initial'
