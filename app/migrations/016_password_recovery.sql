ALTER TABLE {schema}.access_users ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;
CREATE TABLE IF NOT EXISTS {schema}.access_password_resets (
 token_hash text PRIMARY KEY, user_id uuid NOT NULL REFERENCES {schema}.access_users(id) ON DELETE CASCADE,
 expires timestamptz NOT NULL, created timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS access_password_resets_user ON {schema}.access_password_resets(user_id);
CREATE TABLE IF NOT EXISTS {schema}.access_recovery_limits (
 key_hash text PRIMARY KEY, window_start timestamptz NOT NULL DEFAULT now(), attempts integer NOT NULL
);
