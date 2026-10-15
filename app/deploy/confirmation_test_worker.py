"""Explicit, time-bounded staging mail test using existing transactional dispatch.

Only the configured recipient and registrations created after worker activation
are eligible. Existing order IDs are excluded even if subsequently modified.
The application itself retains staging restrictions on every other provider.
"""
import datetime, json, os, time
from pathlib import Path
from psycopg import sql


def scope(store, recipient, expires, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    expiry = datetime.datetime.fromisoformat(expires.replace('Z', '+00:00'))
    if recipient != 'blaze@regfire.events' or expiry.tzinfo is None or not now < expiry <= now + datetime.timedelta(hours=24):
        raise ValueError('Use the designated recipient and a future expiry within 24 hours.')
    with store.connect() as c:
        old = {str(r[0]) for r in c.execute(sql.SQL('SELECT id FROM {}').format(sql.Identifier(store.schema,'registration_orders')))}
    return {'recipient':recipient, 'activated':now, 'expires':expiry, 'existing':old}


def run_once(store, settings, policy, *, now=None):
    from confirmation_delivery import dispatch
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now >= policy['expires']:
        return {'state':'expired', 'submitted':0, 'failed':0}
    with store.connect() as c:
        rows = c.execute(sql.SQL("SELECT order_id FROM {} WHERE status='queued' AND recipient=%s AND updated>=%s ORDER BY updated LIMIT 100").format(sql.Identifier(store.schema,'confirmation_delivery')),(policy['recipient'],policy['activated'])).fetchall()
    result={'state':'active','submitted':0,'failed':0}
    for row in rows:
        ident=str(row[0])
        if ident in policy['existing']:continue
        try:
            dispatch(store,settings,ident)
            result['submitted']+=1
        except Exception:
            with store.connect() as c:
                c.execute(sql.SQL("UPDATE {} SET status='blocked',updated=now() WHERE order_id=%s AND status='queued'").format(sql.Identifier(store.schema,'confirmation_delivery')),(ident,))
            result['failed']+=1
    return result


def main():
    import sys
    sys.path.insert(0,'/app')
    from database import Store
    from communications_settings import Settings
    from confirmation_delivery import readiness
    config=json.loads(os.environ.pop('CONFIRMATION_SETTINGS_JSON'))
    assert config['public_url']=='https://staging.regfire.events'
    assert config['email']['provider']=='bird'
    config['sms']={'provider':'bird','account_sid':'','sender':'','auth_token':''}
    root=Path('/app/.local');root.mkdir(mode=0o700,exist_ok=True);os.chmod(root,0o700)
    path=root/'communications.json';path.write_text(json.dumps(config));os.chmod(path,0o600)
    store=Store(dict(host=os.environ['DB_HOST'],port=5432,dbname='regfire',user='regfire_runtime',password=os.environ.pop('DB_PASSWORD'),sslmode='verify-full',sslrootcert='/app/deploy/rds-ca.pem'))
    if os.getuid()==0:
        os.chown(root,10001,10001);os.chown(path,10001,10001);os.setgroups([]);os.setgid(10001);os.setuid(10001)
    settings=Settings(path)
    policy=scope(store,os.environ['CONFIRMATION_TEST_RECIPIENT'],os.environ['CONFIRMATION_TEST_EXPIRES'])
    # These flags apply only to this narrowly scoped worker, not the web service.
    os.environ.update(REGFIRE_STAGING='0',REGFIRE_COMMUNICATIONS_LIVE='1',REGFIRE_CONFIRMATION_EMAIL_LIVE='1')
    problems=readiness(settings)
    if problems:raise RuntimeError('Confirmation settings are not ready.')
    print(json.dumps({'state':'active','recipient':policy['recipient'],'activated':policy['activated'].isoformat(),'expires':policy['expires'].isoformat(),'excluded_existing_orders':len(policy['existing'])}),flush=True)
    while datetime.datetime.now(datetime.timezone.utc)<policy['expires']:
        result=run_once(store,settings,policy)
        if result['submitted'] or result['failed']:print(json.dumps(result),flush=True)
        time.sleep(10)
    print('Controlled automatic confirmation window expired.',flush=True)

if __name__=='__main__':main()
