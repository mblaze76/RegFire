-- Owner recovery is issued only by the separately authorized operations role.
-- Ordinary email recovery continues to exclude owners.
CREATE TABLE IF NOT EXISTS {schema}.access_owner_recovery_approvals (
 token_hash TEXT PRIMARY KEY REFERENCES {schema}.access_password_resets(token_hash) ON DELETE CASCADE,
 approved_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
