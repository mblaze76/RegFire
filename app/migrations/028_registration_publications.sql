CREATE TABLE IF NOT EXISTS {schema}.registration_publications (
 flow_id UUID PRIMARY KEY REFERENCES {schema}.registration_flows(id) ON DELETE CASCADE,
 published BOOLEAN NOT NULL DEFAULT FALSE,
 revision INTEGER NOT NULL DEFAULT 0
);
