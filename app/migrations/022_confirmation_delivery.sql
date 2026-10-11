CREATE TABLE IF NOT EXISTS {schema}.confirmation_delivery (
 order_id UUID PRIMARY KEY REFERENCES {schema}.registration_orders(id) ON DELETE CASCADE,
 recipient TEXT NOT NULL,
 status TEXT NOT NULL CHECK (status IN ('queued','blocked','submitting','submitted','unknown')),
 provider_id TEXT,
 updated TIMESTAMPTZ NOT NULL DEFAULT now()
);
