CREATE TABLE IF NOT EXISTS {schema}.registration_flows (
    id UUID PRIMARY KEY REFERENCES {schema}.events(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES {schema}.events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    position INTEGER NOT NULL
);
INSERT INTO {schema}.registration_flows(id,event_id,name,kind,position)
SELECT id,id,'Attendee','attendee',0 FROM {schema}.events
WHERE NOT (body ? 'parent_event_id') ON CONFLICT(id) DO NOTHING;
ALTER TABLE {schema}.registration_flows ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
