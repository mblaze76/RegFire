-- Private attendee photo subjects are independent of future registration/badge records.
CREATE TABLE IF NOT EXISTS {schema}.attendee_photos (
 id UUID PRIMARY KEY,
 event_id UUID NOT NULL REFERENCES {schema}.events(id) ON DELETE CASCADE,
 attendee_name TEXT NOT NULL,
 attendee_email TEXT NOT NULL,
 token_hash TEXT UNIQUE NOT NULL,
 expires TIMESTAMPTZ NOT NULL,
 revoked BOOLEAN NOT NULL DEFAULT FALSE,
 attempts INTEGER NOT NULL DEFAULT 0,
 attempt_day DATE NOT NULL DEFAULT CURRENT_DATE,
 lease UUID,
 lease_until TIMESTAMPTZ,
 photo BYTEA,
 screening JSONB,
 approved_at TIMESTAMPTZ,
 created TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK (octet_length(photo) <= 1048576)
);
CREATE INDEX IF NOT EXISTS attendee_photos_event_idx ON {schema}.attendee_photos(event_id);
