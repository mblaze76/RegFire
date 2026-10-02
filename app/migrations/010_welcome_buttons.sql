-- Freeze existing labels and destinations once; subsequent flow renames are independent.
INSERT INTO {schema}.welcome_pages(event_id,body,updated)
SELECT e.id,jsonb_build_object('event_id',e.id,'about','','logo_asset_id',NULL,'sponsor_asset_ids',jsonb_build_array(),'status','draft'),e.updated
FROM {schema}.events e WHERE NOT (e.body ? 'parent_event_id')
ON CONFLICT(event_id) DO NOTHING;
UPDATE {schema}.welcome_pages w SET body=w.body || jsonb_build_object('buttons',
 COALESCE((SELECT jsonb_agg(jsonb_build_object('id',f.id,'label',f.name,'flow_id',f.id) ORDER BY f.position,f.id)
 FROM {schema}.registration_flows f WHERE f.event_id=w.event_id AND NOT f.archived),jsonb_build_array()))
WHERE NOT (w.body ? 'buttons') OR w.body->'buttons'='null'::jsonb;
