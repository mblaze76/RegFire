-- New communications records only. No account/event/member row changes.
CREATE TABLE IF NOT EXISTS {schema}.comm_audiences (
 id UUID PRIMARY KEY, event_id UUID NOT NULL REFERENCES {schema}.events(id) ON DELETE CASCADE,
 name TEXT NOT NULL, recipients JSONB NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
 updated TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(id,event_id)
);
CREATE TABLE IF NOT EXISTS {schema}.comm_campaigns (
 id UUID PRIMARY KEY, event_id UUID NOT NULL REFERENCES {schema}.events(id) ON DELETE CASCADE,
 created_by UUID NOT NULL REFERENCES {schema}.access_users(id), audience_id UUID NOT NULL REFERENCES {schema}.comm_audiences(id),
 name TEXT NOT NULL, channel TEXT NOT NULL CHECK(channel IN ('email','sms')),
 subject TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
 scheduled_at TIMESTAMPTZ, revision INTEGER NOT NULL DEFAULT 1,
 created TIMESTAMPTZ NOT NULL DEFAULT now(), updated TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(id,event_id), FOREIGN KEY(audience_id,event_id) REFERENCES {schema}.comm_audiences(id,event_id)
);
CREATE INDEX IF NOT EXISTS comm_due_campaigns ON {schema}.comm_campaigns(scheduled_at) WHERE status='scheduled';
-- Future inbound routing must bind an external conversation to exactly one authorized event.
CREATE TABLE IF NOT EXISTS {schema}.comm_conversations (
 id UUID PRIMARY KEY, event_id UUID NOT NULL REFERENCES {schema}.events(id) ON DELETE CASCADE,
 channel TEXT NOT NULL CHECK(channel IN ('email','sms')), provider TEXT NOT NULL,
 local_address TEXT NOT NULL, remote_address TEXT NOT NULL,
 created TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(id,event_id), UNIQUE(provider,channel,local_address,remote_address)
);
CREATE TABLE IF NOT EXISTS {schema}.comm_messages (
 id UUID PRIMARY KEY, event_id UUID NOT NULL REFERENCES {schema}.events(id) ON DELETE CASCADE,
 campaign_id UUID REFERENCES {schema}.comm_campaigns(id) ON DELETE CASCADE,
 conversation_id UUID REFERENCES {schema}.comm_conversations(id),
 channel TEXT NOT NULL CHECK(channel IN ('email','sms')), direction TEXT NOT NULL CHECK(direction IN ('inbound','outbound')),
 peer TEXT NOT NULL, body TEXT NOT NULL, provider TEXT NOT NULL, provider_message_id TEXT,
 status TEXT NOT NULL, created TIMESTAMPTZ NOT NULL DEFAULT now(),
 UNIQUE(provider,provider_message_id), UNIQUE(campaign_id,channel,peer,direction),
 FOREIGN KEY(campaign_id,event_id) REFERENCES {schema}.comm_campaigns(id,event_id),
 FOREIGN KEY(conversation_id,event_id) REFERENCES {schema}.comm_conversations(id,event_id)
);
CREATE TABLE IF NOT EXISTS {schema}.comm_delivery_events (
 id UUID PRIMARY KEY, message_id UUID NOT NULL REFERENCES {schema}.comm_messages(id) ON DELETE CASCADE,
 provider TEXT NOT NULL, provider_event_id TEXT NOT NULL, status TEXT NOT NULL,
 received TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(provider,provider_event_id)
);
