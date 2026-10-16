CREATE TABLE IF NOT EXISTS {schema}.partial_registrations (
 id UUID PRIMARY KEY,
 flow_id UUID NOT NULL REFERENCES {schema}.registration_flows(id) ON DELETE CASCADE,
 account_id UUID NOT NULL REFERENCES {schema}.attendee_accounts(id) ON DELETE CASCADE,
 body JSONB NOT NULL,
 publication_digest TEXT NOT NULL,
 created TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated TIMESTAMPTZ NOT NULL DEFAULT now(),
 expires TIMESTAMPTZ NOT NULL,
 email_status TEXT NOT NULL DEFAULT 'not_sent' CHECK(email_status IN ('not_sent','submitting','submitted','unknown')),
 provider_id TEXT,
 token_hash TEXT,
 token_expires TIMESTAMPTZ,
 UNIQUE(flow_id,account_id)
);
CREATE INDEX IF NOT EXISTS partial_registration_expiry ON {schema}.partial_registrations(expires);
