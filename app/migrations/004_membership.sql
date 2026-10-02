CREATE TABLE IF NOT EXISTS {schema}.membership_settings (
 event_id UUID PRIMARY KEY REFERENCES {schema}.events(id) ON DELETE CASCADE,
 body JSONB NOT NULL, updated TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS {schema}.membership_imports (
 event_id UUID PRIMARY KEY REFERENCES {schema}.events(id) ON DELETE CASCADE,
 records JSONB NOT NULL, digest TEXT NOT NULL, updated TIMESTAMPTZ NOT NULL
);
