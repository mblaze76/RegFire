# Background membership lookup

Membership is organizer-only configuration under Event details and is **disabled by default**. There is no attendee membership page or membership preview pane. API connection settings live in My products → Client settings → Membership integration; imported CSVs and eligibility policy remain in Membership setup. Enable it, select one or more member RegTypes and choose a source and policy. Other RegTypes need no check. No attendee registrations, payments or manual review queue exist in this local edition.

- **Require verified membership:** an active, unexpired ID/email match qualifies; otherwise preview continuation is blocked and member pricing is withheld.
- **Allow pending manual review:** an unverified result allows provisional preview continuation with **Price pending**. Organizer diagnostics retain the underlying reason; member pricing is not confirmed. No actual review task is created.

No match, inactive, expired and service unavailable are separate outcomes. An outage never becomes a false verification. If both ID and email are entered, both must match the same record. IDs are case-sensitive; emails are normalized case-insensitively. Expiration is a date inclusive through that date in the event timezone; the member expires at the start of the next local day. Blank means no expiration. The check uses the current time, not the registration price preview clock.

## CSV

Choose a UTF-8 comma-separated file, map four distinct columns (member ID, email, active status, expiration), and click **Preview import**. The server validates every row and shows counts plus a masked sample of up to three rows. It never returns the full saved roster to the browser. The organizer's selected file is necessarily read by their browser for upload.

Click **Replace this event’s member list** and confirm the named event scope. Replacement is atomic and checks the current list revision, so a stale preview cannot overwrite a changed import. Duplicate nonblank IDs or emails reject the entire file. Each row requires at least an ID or email. Active values: active/inactive, true/false, yes/no, 1/0. Expiration: YYYY-MM-DD or blank. Limits: 2 MB and 10,000 members. Keep your source CSV and database backups; there is no roster export or undo UI.

`examples/members-synthetic.csv` contains only fictitious data.

## Supported API adapter

This version supports one shape, not arbitrary provider APIs:

- HTTPS on port 443, POST JSON `{"member_id":"…","email":"…"}`.
- HTTP 200 with `application/json` and either `{"member":null}` or `{"member":{...}}`.
- Map `member_id`, `email`, `active`, `expires` to dotted JSON paths inside `member`. Strings for identity/date and a boolean or supported active-status string are required. An empty date string means no expiration.
- A returned record must match every supplied lookup key. Invalid, mismatched, oversized and non-200 responses become unavailable, not verified.
- Optional bearer auth uses a **server environment variable name** beginning `REGFIRE_MEMBERSHIP_`. Enter only its name in the UI. Configure the value privately in the server environment and restart the app. Never paste tokens into chat or the endpoint. The app does not save or return token values.

Only public DNS/IP targets are allowed. Every resolved address is checked; connections pin an approved address with hostname certificate validation. Private, loopback, link-local, reserved and multicast addresses are blocked. Redirects, URL credentials, query parameters and fragments are rejected. Connection/socket timeout is 5 seconds; response reading has a 10-second deadline and a 64 KiB bound. DNS resolution uses the operating system resolver and its timeout. No provider response body or credential is placed in error messages or HTTP request logs.

**Test API connection** uses the entered ID/email and current unsaved adapter settings. An explicit no-match response still confirms the adapter shape. No live provider credentials were supplied, so external provider compatibility is unverified. A provider with a different protocol needs its own compatible server adapter.

Use `fixture://demo` to test entirely locally. IDs: `DEMO-ACTIVE`, `DEMO-INACTIVE`, `DEMO-EXPIRED`, `DEMO-UNAVAILABLE`. The screen clearly identifies synthetic results. This is not a real membership service.

Membership settings/imports remain registration-flow-scoped in PostgreSQL. Moving the controls does not migrate or delete saved connections or member records. RegTypes referenced by membership cannot be removed until assignments are updated. Imported member data is private local database content; use appropriate disk/account access and protected backups. Existing product grants and event assignments protect integration reads, writes, tests, and background checks. This local edition remains loopback-only; it is not a public registration/checkout service.

## Field triggers and attendee behavior

In Attendee details, each field has **Background membership lookup**: Don’t use for membership, Member email, or Member ID. Text and email fields support lookup; other types do not. Legacy fields default to no lookup, and their saved definitions are retained. At most one field per lookup key may be visible for any one RegType; different RegTypes may use different fields.

Marked visible field values trigger a debounced background check in both the embedded registration preview and the separate attendee preview. Unmarked and hidden field values are not sent to the lookup. If both a member ID and email are supplied, they must match the same record. A stale response cannot re-enable continuation after values or RegType change. Submission checks eligibility again. Success adds no membership UI; failures stay inline on the same form with a retry control. This remains a preview, not live registration/payment enforcement.

The server reads the saved membership policy and connection; field-check requests cannot override them. Disabled/non-member RegTypes do not require a lookup. Required verification holds continuation and pricing; pending policy allows provisional continuation with price marked pending. API outages never produce verified status. Configure at least one visible lookup field when enabling membership for a RegType; otherwise required verification cannot complete.

Client settings updates only the connection and rejects stale connection saves. Membership setup saves omit API settings, so a stale editor cannot overwrite a newer connection. Credential values remain in server environment variables. Connection testing uses explicitly entered test identities; fixture://demo never contacts an external service.

Old /membership bookmarks redirect directly to the flow’s registration details preview. Legacy membership title/font/color fields stay in the stored configuration for compatibility, but no introduction editor or attendee page renders them.
