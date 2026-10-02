CREATE TABLE IF NOT EXISTS {schema}.registration_assets (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES {schema}.events(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('logo', 'background')),
    filename TEXT NOT NULL UNIQUE,
    mime TEXT NOT NULL CHECK (mime = 'image/png'),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    created TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS registration_assets_event_idx ON {schema}.registration_assets(event_id);
