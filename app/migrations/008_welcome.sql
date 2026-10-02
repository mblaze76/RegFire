CREATE TABLE IF NOT EXISTS {schema}.welcome_pages (
    event_id UUID PRIMARY KEY REFERENCES {schema}.events(id) ON DELETE CASCADE,
    body JSONB NOT NULL,
    updated TIMESTAMPTZ NOT NULL
);
