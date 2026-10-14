CREATE TABLE IF NOT EXISTS {schema}.payment_preferences (
 flow_id UUID PRIMARY KEY REFERENCES {schema}.registration_flows(id) ON DELETE CASCADE,
 body JSONB NOT NULL,
 revision INTEGER NOT NULL DEFAULT 0
);
