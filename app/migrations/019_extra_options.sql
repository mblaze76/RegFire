CREATE TABLE IF NOT EXISTS {schema}.extra_options (
 event_id UUID PRIMARY KEY REFERENCES {schema}.events(id) ON DELETE CASCADE,
 body JSONB NOT NULL,
 revision INTEGER NOT NULL DEFAULT 0
);
