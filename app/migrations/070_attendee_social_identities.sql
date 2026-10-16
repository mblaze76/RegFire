CREATE TABLE IF NOT EXISTS {schema}.attendee_social_identities (
 issuer TEXT NOT NULL, subject TEXT NOT NULL,
 account_id UUID NOT NULL REFERENCES {schema}.attendee_accounts(id) ON DELETE CASCADE,
 created TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(issuer,subject), UNIQUE(issuer,account_id)
);
ALTER TABLE {schema}.attendee_sessions ADD COLUMN IF NOT EXISTS auth_method TEXT NOT NULL DEFAULT 'password';
ALTER TABLE {schema}.attendee_sessions ADD COLUMN IF NOT EXISTS authenticated_at TIMESTAMPTZ;
