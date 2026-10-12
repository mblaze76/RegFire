CREATE TABLE IF NOT EXISTS {schema}.attendee_accounts (
 id UUID PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 created TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS {schema}.attendee_enrollments (
 token_hash TEXT PRIMARY KEY, actor_id UUID NOT NULL, flow_id UUID NOT NULL,
 email TEXT NOT NULL, password_hash TEXT NOT NULL, account_id UUID,
 order_id UUID UNIQUE REFERENCES {schema}.registration_orders(id),
 expires TIMESTAMPTZ NOT NULL DEFAULT now()+interval '2 hours'
);
CREATE TABLE IF NOT EXISTS {schema}.attendee_order_access (
 order_id UUID PRIMARY KEY REFERENCES {schema}.registration_orders(id),
 account_id UUID NOT NULL REFERENCES {schema}.attendee_accounts(id)
);
CREATE TABLE IF NOT EXISTS {schema}.attendee_sessions (
 token_hash TEXT PRIMARY KEY, account_id UUID NOT NULL REFERENCES {schema}.attendee_accounts(id),
 csrf TEXT NOT NULL, expires TIMESTAMPTZ NOT NULL DEFAULT now()+interval '8 hours'
);
