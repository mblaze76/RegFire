-- Additive migration. {schema} is safely quoted by Store.initialize().
-- One draft definition per event. No event rows are changed.
CREATE TABLE IF NOT EXISTS {schema}.registration_pages (
    event_id UUID PRIMARY KEY REFERENCES {schema}.events(id) ON DELETE CASCADE,
    body JSONB NOT NULL,
    updated TIMESTAMPTZ NOT NULL
);
