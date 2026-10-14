"""Materialize task secrets privately, then drop privileges. No provider key copied."""
import json,os
from pathlib import Path
root=Path('/app/.local');root.mkdir(mode=0o700,exist_ok=True);os.chmod(root,0o700)
config=dict(host=os.environ['DB_HOST'],port=5432,dbname='regfire',user=os.environ.get('DB_USER','regfire_runtime'),password=os.environ.pop('DB_PASSWORD'),sslmode='verify-full',sslrootcert='/app/deploy/rds-ca.pem')
path=root/'postgres.json';path.write_text(json.dumps(config));os.chmod(path,0o600)
for name in ('REGFIRE_COMMUNICATIONS_LIVE','REGFIRE_CONFIRMATION_EMAIL_LIVE'):os.environ.pop(name,None)
os.environ['REGFIRE_STAGING']='1'
if os.getuid()==0:
 # Fargate mounts the writable temp volume root-owned; set standard sticky permissions.
 os.chmod("/tmp",0o1777)
 os.chown(root,10001,10001);os.chown(path,10001,10001);os.setgroups([]);os.setgid(10001);os.setuid(10001)
os.execvp('gunicorn',['gunicorn','--config','deploy/gunicorn.conf.py','production_wsgi:application'])
