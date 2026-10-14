CREATE TABLE IF NOT EXISTS {schema}.photo_profiles (
 id UUID PRIMARY KEY, name TEXT NOT NULL, provider TEXT NOT NULL CHECK(provider='google_vision'),
 source TEXT NOT NULL CHECK(source IN ('stored','legacy')), secret TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS {schema}.photo_profile_assignments (
 event_id UUID PRIMARY KEY REFERENCES {schema}.events(id) ON DELETE CASCADE,
 profile_id UUID REFERENCES {schema}.photo_profiles(id), revision INTEGER NOT NULL DEFAULT 0
);
WITH first_run AS (
 INSERT INTO {schema}.photo_profiles(id,name,provider,source)
 VALUES('00000000-0000-4000-8000-000000000025','Existing server connection','google_vision','legacy')
 ON CONFLICT DO NOTHING RETURNING id
)
INSERT INTO {schema}.photo_profile_assignments(event_id,profile_id)
SELECT e.id,p.id FROM {schema}.events e CROSS JOIN first_run p
WHERE NOT (e.body ? 'parent_event_id') AND e.body->'photo_upload'->>'enabled'='true'
ON CONFLICT DO NOTHING;
