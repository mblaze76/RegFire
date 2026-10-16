"""Explicitly enabled synthetic staging flows; no organizer grants are conferred."""
import io,json,os,re,secrets,uuid,hmac
from urllib.parse import urlsplit,parse_qs
from psycopg import sql
import psycopg
from access import AccessError,email
from deployment_config import DeploymentConfig

UUID=r'[a-f0-9-]{36}'
READ={'flow-preview','registration-page','demographics','sessions','extra-options','event-footer'}
POST={'pricing-preview','demographics-preview','membership/check-fields','attendee-account','checkout/quote','checkout/group-quote','checkout/save','checkout/group-save','partial-draft','resume-draft'}

def enabled(store,flow):
    allowed=os.environ.get('REGFIRE_STAGING_FLOW_IDS','').split(',')
    if flow not in allowed:
        if not re.fullmatch(UUID,flow or ''):return False
        return __import__('publication').enabled(store,flow)
    with store.connect() as c:
        return bool(c.execute(sql.SQL('SELECT 1 FROM {} WHERE id=%s AND NOT archived').format(sql.Identifier(store.schema,'registration_flows')),(flow,)).fetchone())

def account(h,flow,data):
    import attendee_accounts as aa
    aa.throttle(('public-account',h.client_address[0]))
    address=email(data.get('email'));password=data.get('password')
    if not isinstance(password,str) or not hmac.compare_digest(password,data.get('confirm_password','')):
        raise AccessError('Passwords must match.')
    encoded=aa.password_hash(password)
    with h.server.store.connect() as c:
        c.execute(sql.SQL('INSERT INTO {}(id,email,password_hash) VALUES(%s,%s,%s) ON CONFLICT(email) DO NOTHING').format(aa.table(h.server.store,'attendee_accounts')),(str(uuid.uuid4()),address,encoded))
        row=c.execute(sql.SQL('SELECT id,password_hash FROM {} WHERE email=%s').format(aa.table(h.server.store,'attendee_accounts')),(address,)).fetchone()
        if not aa.password_ok(password,row[1]):raise AccessError('Use the password for this attendee email.',401)
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
        c.execute(sql.SQL('INSERT INTO {}(token_hash,account_id,csrf,authenticated_at) VALUES(%s,%s,%s,now())').format(aa.table(h.server.store,'attendee_sessions')),(aa.digest(token),row[0],csrf))
    enrollment=aa.prepare(h.server.store,str(row[0]),flow,dict(email=address,password=password,confirm_password=password,preview=False))
    aa.respond(h,200,dict(enrollment_token=enrollment,message='Your attendee account is ready. Continue your registration.'),token)

def handle(h):
    try:return contextual_handle(h)
    except (ValueError,TypeError):h.respond(404,{'error':'Registration not found.'});return True
    except psycopg.Error:h.respond(503,{'error':'Registration storage is unavailable.'});return True

def contextual_handle(h):
    # Context is scoped to this request/thread, never to the shared HTTP server.
    match=re.fullmatch('/api/public/events/('+UUID+')/(.+)',urlsplit(h.path).path)
    flow=match[1] if match else None
    order=re.fullmatch('/api/public/checkout/('+UUID+')/(.+)',urlsplit(h.path).path)
    if order:
        uuid.UUID(order[1])
        with h.server.store.connect() as c:
            row=c.execute(sql.SQL('SELECT flow_id FROM {} WHERE id=%s').format(sql.Identifier(h.server.store.schema,'registration_orders')),(order[1],)).fetchone()
        if row:flow=str(row[0])
    if flow:
        try:uuid.UUID(flow)
        except ValueError:h.respond(404,{'error':'Registration not found.'});return True
        from publication_snapshot import load,using
        snapshot=load(h.server.store,flow)
        with using(h.server.store,flow,snapshot):return _handle(h)
    return _handle(h)

def _handle(h):
    path=urlsplit(h.path).path
    if path=='/api/linkedin/status' and h.command=='GET' and os.environ.get('REGFIRE_STAGING_FLOW_IDS') and 'purpose=signin' not in h.path:
        h.respond(200,{'available':False});return True
    if path=='/api/address-config' and h.command=='GET' and os.environ.get('REGFIRE_STAGING_FLOW_IDS'):
        h.respond(200,{'configured':False,'provider':None,'fixture':False,'message':'Enter the address manually in staging.'});return True
    if path=='/api/public/status' and h.command=='GET':
        flow=parse_qs(urlsplit(h.path).query).get('flow',[''])[0]
        h.respond(200,{'enabled':bool(re.fullmatch(UUID,flow) and enabled(h.server.store,flow))});return True
    match=re.fullmatch('/api/public/events/('+UUID+')/(.+)',path)
    order=re.fullmatch('/api/public/checkout/('+UUID+')/(status|start|confirmation(?:/receipt.pdf)?)',path)
    if not match and not order:return False
    try:
        store=h.server.store
        if h.command not in ('GET','POST'):raise AccessError('Not found.',404)
        if h.command=='POST' and not DeploymentConfig.load(h.server.server_port).allows_origin(h.headers.get('Origin'),h.headers.get('Host','')):raise AccessError('Use this registration page.',403)
        from attendee_accounts import identity
        who=identity(h)
        if order:
            if not who:raise AccessError('Sign in to your attendee account.',401)
            with store.connect() as c:
                row=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s AND actor_id=%s').format(sql.Identifier(store.schema,'registration_orders')),(order[1],who['id'])).fetchone()
            if not row:raise AccessError('Registration not found.',404)
            flow=row[0]['flow_id'];action=order[2]
            if (action=='start')!=(h.command=='POST'):raise AccessError('Not found.',404)
        else:
            flow,action=match.groups()
            if h.command=='GET' and action not in READ and not re.fullmatch('assets/'+UUID,action) and action!='checkout/methods':raise AccessError('Not found.',404)
            if h.command=='POST' and action not in POST:raise AccessError('Not found.',404)
        if not enabled(store,flow):raise AccessError('Registration is unavailable.',404)
        data={}
        if h.command=='POST':
            size=int(h.headers.get('Content-Length','0'))
            if not 0<size<=1000000:raise AccessError('Invalid request size.')
            data=json.loads(h.rfile.read(size))
            if not isinstance(data,dict):raise AccessError('Send an object.')
            if action=='attendee-account':account(h,flow,data);return True
        protected=bool(order or action in ('checkout/save','checkout/group-save','partial-draft','resume-draft'))
        if protected:
            if not who:raise AccessError('Create or sign in to your attendee account using the registration form.',401)
            if h.command=='POST' and not hmac.compare_digest(h.headers.get('X-Attendee-CSRF',''),who['csrf']):raise AccessError('Refresh registration before continuing.',403)
        if action in ('partial-draft','resume-draft'):
            from partial_registration import save,resume
            value=save(store,flow,who['id'],data) if action=='partial-draft' else resume(store,flow,who['id'],data.get('token'))
            h.respond(200,value);return True
        # The identity is only accepted within this exact flow by checkout.
        h.identity=dict(id=who['id'] if who else str(uuid.UUID(int=0)),role='public-attendee',public_flow=flow)
        if action=='flow-preview':
            with store.connect() as c:row=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()),(flow,)).fetchone()
            from publication_snapshot import current
            snap=current(store,flow)
            if snap:row=(snap['event'],)
            fields=('id','name','start','end','timezone','venue','location','address','format')
            h.respond(200,dict(event={k:row[0][k] for k in fields if k in row[0]},registration=store.registration_page(flow),demographics=store.demographics_page(flow),at='',regtype=None));return True
        if action in ('pricing-preview','demographics-preview'):
            # Never honor organizer preview overrides from an attendee.
            data['page']=store.registration_page(flow) if action=='pricing-preview' else store.demographics_page(flow)
            data['registration_page']=store.registration_page(flow);data.pop('at',None)
        if action=='membership/check-fields':data.pop('registration_page',None)
        h.path=path.replace('/api/public/','/api/',1)
        if h.command=='POST':
            payload=json.dumps(data).encode();h.rfile=io.BytesIO(payload)
            if 'Content-Length' in h.headers:del h.headers['Content-Length']
            h.headers['Content-Length']=str(len(payload))
        getattr(h,'do_'+h.command)()
    except AccessError as exc:h.respond(exc.status,{'error':str(exc)})
    except (ValueError,TypeError,KeyError):h.respond(400,{'error':'Check the registration details.'})
    except psycopg.Error:h.respond(503,{'error':'Registration storage is unavailable.'})
    return True

# Presentation assets contain no event records. Event assets still require an
# enabled flow and exact event/asset association in Store.asset.
PRESENTATION={'/payment-demo.js','/payment-demo.css','/apple-wallet-official.svg','/google-wallet-official.svg','/register','/sessions','/extras','/review','/payment','/confirmation',
 '/attendee-branding.js','/attendee-journey.js','/field-validation.js','/badge-preview.js',
 '/subcategories.js','/linkedin-import.js','/background-membership.js','/address.js',
 '/footer.js','/email.js','/welcome-fonts.js','/welcome-common.js','/live-preview.js',
 '/sessions.css','/sessions-common.js','/sessions-site.js','/extras.css','/extras-common.js',
 '/extras-site.js','/checkout-site.js','/confirmation.css','/confirmation-common.js',
 '/regfire-logo-3d-transparent.png','/linkedin-in-official.png'}
def public_presentation(h):
    if h.command!='GET':return False
    if not os.environ.get('REGFIRE_STAGING_FLOW_IDS'):
        if os.environ.get('REGFIRE_ENV','local')=='production' and os.environ.get('REGFIRE_PUBLICATION_ENABLED')!='1':return False
        with h.server.store.connect() as c:
            if not c.execute(sql.SQL('SELECT 1 FROM {} p JOIN {} f ON f.id=p.flow_id WHERE p.published AND NOT f.archived LIMIT 1').format(sql.Identifier(h.server.store.schema,'registration_publications'),sql.Identifier(h.server.store.schema,'registration_flows'))).fetchone():return False
    path=urlsplit(h.path).path
    if path in PRESENTATION:return True
    asset=re.fullmatch('/api/events/('+UUID+')/assets/'+UUID,path)
    if asset and not h.identity and enabled(h.server.store,asset[1]):
        from publication_snapshot import public_asset,load
        if load(h.server.store,asset[1]):
            h.public_asset=public_asset(h.server.store,asset[1],path.rsplit('/',1)[1])
            return bool(h.public_asset)
        return asset[1] in os.environ.get('REGFIRE_STAGING_FLOW_IDS','').split(',')
    if asset and not h.identity:
        from publication_snapshot import public_asset
        h.public_asset=public_asset(h.server.store,asset[1],path.rsplit('/',1)[1])
        return bool(h.public_asset)
    return False
