# Communications connections

Open **My products → Communications** or **Administration → Communications** as the original owner (Super administrator). Administrators, clients, and employees cannot load the page, scripts, or configuration API. Current account status is checked on each request; existing event grants and membership integration placement are unchanged.

## Implemented

- Owner-only SendGrid email and Twilio SMS configuration with sender email/name, Twilio account SID and sending number, and the recovery site origin.
- Private secret entry, keep/replace/remove controls, presence-only masking, optimistic revision checks, and an audit event that contains no configuration or credentials.
- Configuration validation with **no network call**. Configured means required values are present, not that a provider accepted the credentials or verified the sender. There is no live connection test or send endpoint in the UI.
- A common provider adapter boundary: SendGrid email and Twilio SMS return `submitted` with a provider message ID, never `delivered`. HTTPS requests use fixed endpoints, certificate verification, bounded responses, no redirect, and redacted errors. Future features use the adapter registry, not provider-specific code in each feature.
- Existing password recovery tokens, limits, expiry, owner exclusion, revocation, and administrator reset codes are preserved. Until shared settings are explicitly saved, the existing private SMTP transport remains in use. After saving, shared settings select SendGrid or the existing SMTP transport. No SMTP credentials are copied or exposed.

## Storage and activation

Credentials are held in `app/.local/communications.json` on the server, not PostgreSQL or browser storage. The file is mode 0600, its containing directory must be private, and saves use locking plus atomic replacement. This is filesystem access protection, not application-level encryption. Protect the machine and any private backup accordingly. The file and lock must never enter Git or a deployment bundle. Browser fields are cleared after a save attempt, and the API never returns secret values or suffixes.

Live recovery delivery using shared settings additionally requires the server environment gate `REGFIRE_COMMUNICATIONS_LIVE=1`. It defaults off; the UI does not set it. **Do not enable it until the user authorizes live delivery and completes account/sender setup.** Saving shared settings with the gate off disables shared recovery delivery; administrator codes remain available. The page shows the gate status.

The user supplies credentials privately in the owner page. SendGrid requires a usable API key and verified sender/domain; Twilio requires the user's account credentials and an activated, messaging-capable sending number. No accounts, keys, numbers, DNS changes, paid plans, or real sends are created by this implementation. Configure the correct recovery origin before activation. This app is still loopback-only; a public deployment needs its own HTTPS and hosting work.

## Future client campaigns and two-way SMS

There is **no client dashboard, audience editor, scheduler, campaign sender, result dashboard, reply endpoint, or inbox** in this change. Migration 017 provides additive, unused schema foundations only:

- `comm_audiences` and `comm_campaigns` bind future audience and campaign records to an event, with revisions and scheduling timestamps.
- `comm_conversations` maps provider/channel/local address/remote address to one event. The unique routing key prevents silently sharing an inbound conversation between clients. Resolving reuse across multiple events will require an explicit routing decision.
- `comm_messages` records event, optional campaign/conversation, inbound/outbound direction, provider identity, body and status. Unique provider-message IDs and outbound campaign-recipient keys prepare idempotent handling.
- `comm_delivery_events` stores deduplicated provider status events separately from submission.

Before exposing these tables through APIs, enforce current product/event grants on every audience, message, schedule and result operation, including background processing. Consent and suppression handling, recipient validation, unsubscribe/STOP behavior, delivery retries/unknown outcomes, authenticated webhook signatures, replay protection, public webhook routing, retention, and an event-scoped inbox remain future implementation work. Never infer delivery from an accepted API request. No inbound handler is exposed now, so the existing same-origin/CSRF protection has no webhook exemption.

Provider references used for the adapters and future boundary:
- [SendGrid Mail Send](https://www.twilio.com/docs/sendgrid/api-reference/mail-send/mail-send)
- [Twilio Message resource](https://www.twilio.com/docs/messaging/api/message-resource)
- [Twilio webhook security](https://www.twilio.com/docs/usage/webhooks/webhooks-security)

Tests use disposable PostgreSQL schemas, temporary private settings, and stubbed provider HTTP responses. They never contact a messaging provider.
