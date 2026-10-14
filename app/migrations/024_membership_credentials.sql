CREATE TABLE IF NOT EXISTS {schema}.membership_credentials (event_id UUID PRIMARY KEY REFERENCES {schema}.events(id) ON DELETE CASCADE, endpoint TEXT NOT NULL, token TEXT NOT NULL);
