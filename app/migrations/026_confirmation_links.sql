CREATE TABLE IF NOT EXISTS {schema}.confirmation_links (
 order_id UUID PRIMARY KEY REFERENCES {schema}.registration_orders(id) ON DELETE CASCADE,
 token_hash TEXT NOT NULL UNIQUE,
 expires TIMESTAMPTZ NOT NULL DEFAULT now()+interval '7 days'
);
