-- Preserve existing access to current events once, then use explicit assignments.
ALTER TABLE {schema}.access_users ADD COLUMN IF NOT EXISTS first_name TEXT NOT NULL DEFAULT '';
ALTER TABLE {schema}.access_users ADD COLUMN IF NOT EXISTS last_name TEXT NOT NULL DEFAULT '';
ALTER TABLE {schema}.access_users ADD COLUMN IF NOT EXISTS company_name TEXT NOT NULL DEFAULT '';
ALTER TABLE {schema}.access_users DROP CONSTRAINT IF EXISTS access_users_role_check;
CREATE TABLE IF NOT EXISTS {schema}.access_event_grants (
 user_id UUID REFERENCES {schema}.access_users(id) ON DELETE CASCADE,
 event_id UUID REFERENCES {schema}.events(id) ON DELETE CASCADE,
 PRIMARY KEY(user_id,event_id)
);
INSERT INTO {schema}.access_event_grants(user_id,event_id)
 SELECT u.id,e.id FROM {schema}.access_users u
 JOIN {schema}.access_grants p ON p.user_id=u.id AND p.product_slug='event-builder'
 CROSS JOIN {schema}.events e
 WHERE u.role='user' AND NOT (e.body ? 'parent_event_id') ON CONFLICT DO NOTHING;
UPDATE {schema}.access_users SET role='client' WHERE role='user';
ALTER TABLE {schema}.access_users ALTER COLUMN role SET DEFAULT 'client';
ALTER TABLE {schema}.access_users ADD CONSTRAINT access_users_role_check CHECK(role IN ('owner','admin','client','employee'));
