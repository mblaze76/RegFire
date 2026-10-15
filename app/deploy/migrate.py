"""One-shot privileged migration; runtime never receives this master credential."""
import os,sys
sys.path.insert(0,'/app')
import psycopg
from psycopg import sql
from database import Store
from access import Access,password_hash
cfg=dict(host=os.environ['DB_HOST'],port=5432,dbname='regfire',user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],sslmode='verify-full',sslrootcert='/app/deploy/rds-ca.pem')
s=Store(cfg);s.initialize()
with s.connect() as c:
 if not c.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',('regfire_runtime',)).fetchone():
  c.execute('CREATE ROLE regfire_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION')
 c.execute(sql.SQL('ALTER ROLE regfire_runtime PASSWORD {}').format(sql.Literal(os.environ['RUNTIME_DB_PASSWORD'])))
 c.execute('GRANT CONNECT ON DATABASE regfire TO regfire_runtime')
 c.execute('GRANT USAGE ON SCHEMA regfire TO regfire_runtime')
 c.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA regfire TO regfire_runtime')
 c.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA regfire TO regfire_runtime')
 c.execute('REVOKE INSERT,UPDATE,DELETE ON regfire.access_owner_recovery_approvals FROM regfire_runtime')
 c.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA regfire GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO regfire_runtime')
 c.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA regfire GRANT USAGE,SELECT ON SEQUENCES TO regfire_runtime')
a=Access(s)
if not a.configured():a.bootstrap(os.environ['STAGING_OWNER_EMAIL'],os.environ['STAGING_OWNER_PASSWORD'])
print('Schema migrated; restricted runtime grants and staging owner ready. No credentials logged.')
