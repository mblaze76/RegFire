-- Additive access control. Existing event rows are untouched.
CREATE TABLE IF NOT EXISTS {schema}.access_users (
 id UUID PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT,
 role TEXT NOT NULL CHECK(role IN ('owner','admin','user')) DEFAULT 'user',
 status TEXT NOT NULL CHECK(status IN ('assigned','active','suspended')) DEFAULT 'assigned',
 created TIMESTAMPTZ NOT NULL DEFAULT now(), updated TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS single_access_owner ON {schema}.access_users(role) WHERE role='owner';
CREATE TABLE IF NOT EXISTS {schema}.access_products (
 slug TEXT PRIMARY KEY, name TEXT NOT NULL, enabled BOOLEAN NOT NULL DEFAULT true,
 created TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO {schema}.access_products(slug,name) VALUES ('event-builder','Event builder') ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS {schema}.access_grants (
 user_id UUID REFERENCES {schema}.access_users(id) ON DELETE CASCADE,
 product_slug TEXT REFERENCES {schema}.access_products(slug), PRIMARY KEY(user_id,product_slug)
);
CREATE TABLE IF NOT EXISTS {schema}.access_sessions (
 token_hash TEXT PRIMARY KEY,user_id UUID NOT NULL REFERENCES {schema}.access_users(id) ON DELETE CASCADE,
 csrf TEXT NOT NULL, expires TIMESTAMPTZ NOT NULL, created TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS {schema}.access_enrollments (
 token_hash TEXT PRIMARY KEY,user_id UUID NOT NULL UNIQUE REFERENCES {schema}.access_users(id) ON DELETE CASCADE,
 expires TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS {schema}.access_audit (
 id BIGSERIAL PRIMARY KEY,actor UUID,action TEXT NOT NULL,target TEXT NOT NULL,created TIMESTAMPTZ NOT NULL DEFAULT now()
);
