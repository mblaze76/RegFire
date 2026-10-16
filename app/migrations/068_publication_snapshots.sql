ALTER TABLE {schema}.registration_publications ADD COLUMN IF NOT EXISTS snapshot JSONB;
ALTER TABLE {schema}.registration_publications ADD COLUMN IF NOT EXISTS snapshot_digest TEXT;
ALTER TABLE {schema}.registration_publications ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
