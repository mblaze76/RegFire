CREATE TABLE IF NOT EXISTS {schema}.registration_orders (
 id UUID PRIMARY KEY,
 flow_id UUID NOT NULL REFERENCES {schema}.events(id) ON DELETE RESTRICT,
 actor_id UUID NOT NULL,
 request_key UUID NOT NULL,
 body JSONB NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',
 updated TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(flow_id,actor_id,request_key)
);
CREATE INDEX IF NOT EXISTS registration_orders_flow_status ON {schema}.registration_orders(flow_id,status);
