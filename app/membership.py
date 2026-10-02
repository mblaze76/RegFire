"""Event membership configuration, strict imports, and a bounded HTTPS adapter."""
import csv, io, json, re, hashlib, socket, ssl, http.client, ipaddress, os, time
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

FIELDS=('member_id','email','active','expires')
class Unavailable(Exception): pass

def starter():
    return dict(enabled=False,source='csv',policy='required',regtype_ids=[],api=dict(endpoint='',credential_env='',mapping={k:k for k in FIELDS}))

def endpoint(value):
    if value=='fixture://demo': return value
    u=urlsplit(value)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.fragment or u.query or u.port not in (None,443):
        raise ValueError('Use an HTTPS endpoint on port 443, without credentials, query parameters or fragments; or fixture://demo for synthetic tests.')
    if len(value)>1000 or any(ord(c)<33 for c in value):raise ValueError('Invalid API endpoint.')
    return value

def validate(data, regtypes):
    if not isinstance(data,dict):raise ValueError('Membership settings are required.')
    result=starter()
    if type(data.get('enabled',False)) is not bool:raise ValueError('Choose whether membership checking is enabled.')
    result['enabled']=data.get('enabled',False)
    for key,allowed in [('source',('csv','api')),('policy',('required','pending'))]:
        if data.get(key) not in allowed:raise ValueError('Choose a supported membership '+key+'.')
        result[key]=data[key]
    ids=data.get('regtype_ids',[]);known={r['id'] for r in regtypes}
    if not isinstance(ids,list) or any(not isinstance(x,str) or x not in known for x in ids) or len(set(ids))!=len(ids):raise ValueError('Membership references a missing or duplicate RegType. Update Membership before removing that RegType.')
    if result['enabled'] and not ids:raise ValueError('Select at least one member RegType.')
    result['regtype_ids']=ids
    a=data.get('api',{})
    if not isinstance(a,dict):raise ValueError('Invalid API settings.')
    ep=a.get('endpoint','');env=a.get('credential_env','');mapping=a.get('mapping',{k:k for k in FIELDS})
    if not isinstance(ep,str) or not isinstance(env,str):raise ValueError('API settings must be text.')
    if ep:endpoint(ep)
    if env and not re.fullmatch(r'REGFIRE_MEMBERSHIP_[A-Z0-9_]{1,80}',env):raise ValueError('Use a server environment variable named REGFIRE_MEMBERSHIP_… for the bearer token.')
    if not isinstance(mapping,dict) or set(mapping)!=set(FIELDS) or any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,5}',v) for v in mapping.values()):raise ValueError('Map each member field to a JSON property path.')
    if result['enabled'] and result['source']=='api' and not ep:raise ValueError('Add the membership API endpoint.')
    result['api']=dict(endpoint=ep,credential_env=env,mapping=mapping)
    return result

def clean_record(row):
    if not isinstance(row,dict):raise ValueError('Member response must be an object.')
    result={}
    for k in ('member_id','email','expires'):
        v=row.get(k,'')
        if not isinstance(v,str) or len(v)>254:raise ValueError('Member ID, email and expiration must be text of at most 254 characters.')
        result[k]=v.strip()
    if not result['member_id'] and not result['email']:raise ValueError('Every member needs an ID or email.')
    if result['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',result['email']):raise ValueError('Invalid member email.')
    result['email']=result['email'].casefold()
    active=row.get('active')
    if isinstance(active,str):active={'active':True,'true':True,'yes':True,'1':True,'inactive':False,'false':False,'no':False,'0':False}.get(active.strip().lower())
    if type(active) is not bool:raise ValueError('Active status must be active/inactive, true/false, yes/no, or 1/0.')
    result['active']=active
    if result['expires']:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',result['expires']):raise ValueError('Expiration must be YYYY-MM-DD, or blank for no expiration.')
        try:date.fromisoformat(result['expires'])
        except ValueError:raise ValueError('Invalid expiration date.')
    return result

def parse_csv(content,mapping):
    if not isinstance(content,str) or len(content.encode())>2_000_000:raise ValueError('Choose a UTF-8 CSV no larger than 2 MB.')
    if not isinstance(mapping,dict) or set(mapping)!=set(FIELDS) or any(not isinstance(v,str) or not v for v in mapping.values()) or len(set(mapping.values()))!=4:raise ValueError('Map four distinct columns: member ID, email, active status and expiration.')
    try:
        reader=csv.DictReader(io.StringIO(content.lstrip('\ufeff')),strict=True)
        headers=reader.fieldnames or []
        if len(headers)!=len(set(headers)) or len(headers)>100 or any(v not in headers for v in mapping.values()):raise ValueError('CSV headers are missing, duplicated, or do not match the column mapping.')
        rows=[];seen_id=set();seen_email=set()
        for index,row in enumerate(reader,2):
            if index>10001:raise ValueError('Import at most 10,000 members at a time.')
            if None in row or any(v is None for v in row.values()):raise ValueError(f'Row {index}: column count does not match the header.')
            try:record=clean_record({k:row[v] for k,v in mapping.items()})
            except ValueError as e:raise ValueError(f'Row {index}: {e}')
            for k,seen in [('member_id',seen_id),('email',seen_email)]:
                v=record[k]
                if v and v in seen:raise ValueError(f'Row {index}: duplicate {k.replace("_"," ")}. Resolve duplicates before importing; no rows were changed.')
                if v:seen.add(v)
            rows.append(record)
        if not rows:raise ValueError('The CSV has no member rows. Existing records are unchanged.')
        return rows
    except csv.Error:raise ValueError('Could not read this CSV. Check quoting and delimiters.')

def digest(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def summary(rows):
    return dict(count=len(rows),active_count=sum(r['active'] for r in rows),preview=[dict(member_id=('…'+r['member_id'][-4:]) if r['member_id'] else '',email=(r['email'][:1]+'…@'+r['email'].split('@')[-1]) if r['email'] else '',active=r['active'],expires=r['expires']) for r in rows[:3]],digest=digest(rows))

def lookup_keys(data):
    if not isinstance(data,dict):raise ValueError('Enter a member ID or email.')
    result={k:data.get(k,'') for k in ('member_id','email')}
    if any(not isinstance(v,str) or len(v)>254 for v in result.values()):raise ValueError('Lookup values must be text of at most 254 characters.')
    result={k:v.strip() for k,v in result.items()};result['email']=result['email'].casefold()
    if not any(result.values()):raise ValueError('Enter a member ID or email.')
    if result['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',result['email']):raise ValueError('Enter a valid email.')
    return result

def matches(record,keys):return all(not v or record[k]==v for k,v in keys.items())

def public_addresses(host):
    try:addresses=list(dict.fromkeys(x[4][0] for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
    except OSError:raise Unavailable('Membership service unavailable.')
    if not addresses or any((not ipaddress.ip_address(a).is_global or ipaddress.ip_address(a).is_multicast) for a in addresses):raise Unavailable('API target is blocked. Use a public HTTPS service; private and local addresses are not allowed.')
    return addresses

def trusted_context():
    import certifi
    context=ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,address):super().__init__(host,443,timeout=5,context=trusted_context());self.address=address
    def connect(self):
        # Connect to the exact validated IP; retain hostname for certificate checks and SNI.
        raw=socket.create_connection((self.address,443),timeout=self.timeout)
        try:self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException:raw.close();raise

def https_json(url,payload,token=''):
    endpoint(url);u=urlsplit(url);addresses=public_addresses(u.hostname)
    conn=PinnedHTTPS(u.hostname,addresses[0])
    try:
        headers={'Content-Type':'application/json','Accept':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        conn.request('POST',u.path or '/',body=json.dumps(payload).encode(),headers=headers)
        r=conn.getresponse()
        if r.status!=200 or 'application/json' not in r.getheader('Content-Type','').lower():raise Unavailable('Membership service returned an unsupported response.')
        content=b'';deadline=time.monotonic()+10
        while len(content)<=65536:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise Unavailable('Membership response timed out.')
            if conn.sock:conn.sock.settimeout(min(5,remaining))
            chunk=r.read1(min(8192,65537-len(content)))
            if not chunk:break
            content+=chunk
        if len(content)>65536:raise Unavailable('Membership response is too large.')
        return json.loads(content)
    except (OSError,ValueError,http.client.HTTPException):raise Unavailable('Membership service unavailable or returned invalid data.')
    finally:conn.close()

def api_lookup(config,keys,transport=https_json):
    a=config['api']
    if a['endpoint']=='fixture://demo':
        fixtures=[dict(member_id='DEMO-ACTIVE',email='active@example.test',active=True,expires='2099-12-31'),dict(member_id='DEMO-INACTIVE',email='inactive@example.test',active=False,expires=''),dict(member_id='DEMO-EXPIRED',email='expired@example.test',active=True,expires='2000-01-01')]
        if keys['member_id']=='DEMO-UNAVAILABLE':raise Unavailable('Synthetic service-unavailable fixture.')
        return next((r for r in fixtures if matches(r,keys)),None)
    env=a['credential_env'];token=os.environ.get(env,'') if env else ''
    if env and not token:raise Unavailable('The configured server credential is not set.')
    if len(token)>8192 or any(ord(c)<32 for c in token):raise Unavailable('The server credential is invalid.')
    response=transport(a['endpoint'],keys,token)
    try:
        if not isinstance(response,dict) or 'member' not in response:raise ValueError()
        row=response['member']
        if row is None:return None
        mapped={}
        for key,path in a['mapping'].items():
            value=row
            for part in path.split('.'):
                if not isinstance(value,dict):raise ValueError()
                value=value[part]
            mapped[key]=value
        record=clean_record(mapped)
        if not matches(record,keys):raise ValueError()
        return record
    except (KeyError,ValueError,TypeError):raise Unavailable('Membership service returned invalid or mismatched member data.')

def outcome(config,record,zone,unavailable=False,now=None,applies=True):
    if not config['enabled'] or not applies:return dict(status='not_required',reason='Membership checking is not required for this RegType.',can_continue=True,pricing='Regular RegType pricing applies; no membership claim is made.')
    today=(now or datetime.now(timezone.utc)).astimezone(ZoneInfo(zone)).date()
    status='unavailable' if unavailable else 'no_match' if record is None else 'inactive' if not record['active'] else 'expired' if record['expires'] and date.fromisoformat(record['expires'])<today else 'verified'
    reasons={'verified':'Active, unexpired membership verified.','no_match':'No matching membership was found.','inactive':'The matching membership is inactive.','expired':'The matching membership has expired.','unavailable':'The membership service is unavailable. This is not a failed membership match.'}
    pending=status!='verified' and config['policy']=='pending'
    return dict(status='pending' if pending else status,verification_status=status,reason=reasons[status],can_continue=status=='verified' or pending,pricing='Member RegType pricing is eligible in this preview.' if status=='verified' else 'Member price is provisional and not confirmed; manual review would be required.' if pending else 'Member price is withheld until membership is verified.',notice='Preview only. No registration, payment or review request is created.')
