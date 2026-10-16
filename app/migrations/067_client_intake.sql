CREATE TABLE IF NOT EXISTS {schema}.client_intake_previews (
 id UUID PRIMARY KEY,
 user_id UUID NOT NULL REFERENCES {schema}.access_users(id) ON DELETE CASCADE,
 body JSONB NOT NULL,
 event_id UUID REFERENCES {schema}.events(id) ON DELETE CASCADE,
 expires TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '30 minutes')
);
CREATE INDEX IF NOT EXISTS client_intake_expiry ON {schema}.client_intake_previews(expires);
