CREATE TABLE IF NOT EXISTS {schema}.welcome_page_revisions (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES {schema}.events(id) ON DELETE CASCADE,
    body JSONB NOT NULL,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS welcome_page_revisions_event_idx
    ON {schema}.welcome_page_revisions(event_id, id DESC);
