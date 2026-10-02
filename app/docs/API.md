# HTTP API and validation

Base URL: `http://127.0.0.1:8765`. Browser requests use the local server. Optional, explicitly configured provider adapters can make outbound HTTPS calls. There is no authentication token or public API deployment. JSON responses use `Content-Type: application/json` and `Cache-Control: no-store`.

| Method and path | Behavior | Success |
| --- | --- | --- |
| `GET /` | Event workspace HTML | 200 |
| `GET /app.js`, `GET /builder.js`, `GET /demographics.js`, `GET /membership.js`, `GET /address.js`, `GET /live-editor.js`, `GET /live-preview.js`, `GET /preview`, `GET /style.css`, `GET /regfire-logo.png` | Static assets | 200 |
| `GET /api/timezones` | Sorted timezone strings from Python/system timezone data | 200 array |
| `GET /api/events` | All saved bodies, latest updated first then ID | 200 array; empty array when no drafts |
| `POST /api/events` | Create a draft with server-generated identity/timestamps | 201 event object |
| `GET /api/events/{id}/registration-page` | Saved page definition, or unsaved starter for an existing event | 200 object |
| `POST /api/events/{id}/pricing-preview` | Validate and evaluate unsaved pricing at a test time; no write | 200 object |
| `POST /api/events/{id}/assets/{kind}` | Upload a static image; kind is logo or background | 201 asset metadata |
| `GET /api/events/{id}/assets/{asset_id}` | Read an event-owned PNG | 200 image/png |
| `PUT /api/events/{id}/registration-page` | Replace this event's page draft | 200 object |
| `PUT /api/events/{id}` | Replace editable fields on an existing draft, preserving identity/creation time | 200 event object |

There is no individual-event GET, PATCH, pagination, search or publishing endpoint. PUT is a complete editable-field replacement: omitted optional fields become empty strings. Unknown input properties are ignored; caller-supplied ID, status and timestamps are not trusted.

Minimum create request:

```json
{"name":"Leadership Summit","timezone":"America/New_York","format":"in_person"}
```

For example, read existing drafts without changing them:

```sh
curl --noproxy '*' http://127.0.0.1:8765/api/events
```

## Event validation

The request body must be a JSON object with a declared Content-Length from 1 through 50,000 bytes. The implementation parses JSON but does not enforce a request Content-Type. Send `application/json` and ordinary non-chunked requests.

All editable fields must be strings, trimmed before validation. Description is limited to 10,000 characters; each other editable field is limited to 500. Missing fields become empty strings. Name must be nonblank. Timezone must resolve with Python `ZoneInfo`; format must be exactly `in_person` or `online`.

Start and end may both be blank. A supplied value must match `YYYY-MM-DDTHH:MM` and represent a real local time in the chosen timezone. End requires start and must be strictly later after timezone conversion. Start without end is permitted. See [database time handling](DATABASE.md).

Email is optional; if present, it must match the basic pattern of non-space text, `@`, non-space text, a dot and non-space text. This is a syntax check, not address verification. URL is optional but, if present, must parse with scheme `http` or `https` and a hostname. The server does not visit or verify the destination. Both are validated regardless of event format. Venue, location, description and organizer are optional free text.

## Failures and boundaries

Errors normally return `{"error":"human-readable message"}`:

| Status | Meaning |
| --- | --- |
| 400 | Invalid JSON/text encoding, body length or field validation |
| 403 | A supplied Origin differs from `http://` plus the request Host |
| 404 | Unknown route or edit of an absent event |
| 503 | Psycopg database error during list/save |

Unsupported methods such as DELETE use the underlying HTTP server's 501 response, which is not this JSON error format. PUT route matching accepts 36 lowercase hexadecimal/hyphen characters; a malformed UUID that passes that broad pattern can reach PostgreSQL and produce 503 rather than 400. Startup configuration/file errors are not HTTP responses.

Origin-free requests are accepted. Origin checking is not authentication and does not make public exposure safe. The UI renders user text with `textContent` or form values, not HTML interpolation. There is no API rate limit, idempotency key or revision precondition; if a response is lost after a successful POST, retrying can create another draft.

## Registration-page API

GET returns an event-scoped definition; when unsaved, `updated` is null and starter fields/RegTypes are supplied without writing. A missing event returns 404. PUT accepts a complete definition, not a partial patch, with a Content-Length of 1–500,000 bytes. Client metadata is ignored; event ID, draft status and save timestamp come from the route/server. Missing events return 404; invalid page data or malformed UUIDs return 400; database failures return 503. Writes use the same Origin rule as event writes.

Example complete editable payload:

```json
{
  "title": "Register for the summit",
  "intro": "Choose your RegType.",
  "currency": "USD",
  "regtypes": [
    {"id": "attendee", "name": "Attendee", "price_minor": 12550},
    {"id": "speaker", "name": "Speaker", "price_minor": 0}
  ],
  "fields": [
    {"id": "name", "label": "Full name", "type": "text", "required": true, "options": [], "visible_to": null},
    {"id": "topic", "label": "Session topic", "type": "text", "required": true, "options": [], "visible_to": ["speaker"]}
  ]
}
```

Title is nonblank, maximum 200 characters; intro is optional, maximum 5,000. Fields: 1–50. RegTypes: 1–30. Child IDs must match `[A-Za-z0-9_-]{1,64}` and be unique within their array. Labels are nonblank with at most 120 characters. RegType names are nonblank, at most 80, and unique ignoring case. Strings are trimmed.

Field types are `text`, `email`, `tel`, `textarea`, `select`, `radio`, `checkbox`, `address`. `required` must be a boolean. `options` must be an array; select/radio require 2–30 nonblank, case-insensitively unique strings of at most 120 characters. Other types normalize options to an empty array. `visible_to` is null/missing for all types or a nonempty array of unique, current RegType IDs; stale references reject the whole save.

Currency must be USD/EUR/GBP/CAD/AUD (two decimal places) or JPY (zero). `price_minor` must be an integer, not boolean/string/float, between 0 and 99,999,999. The browser parses decimal input; the API takes only integer minor units. Currency changes do not convert exchange rates. A successful response adds `event_id`, `status: "draft"` and `updated`. No payment or attendee-submission endpoints exist. Required/email answer checks occur only in the local preview for visible fields; the API validates definitions, not attendee answers.

## Date-driven pricing

RegTypes accept optional `use_default` (boolean, default true) and `rates` (array, default empty; maximum 20). Rates contain `id` (same ID syntax; unique per RegType), `name` (nonblank, at most 80; unique ignoring case), `price_minor` (existing exact integer range), `start` and `end` (empty or `YYYY-MM-DDTHH:MM`). At least one boundary is needed. Starts are inclusive, ends exclusive. Windows must not overlap and end must be later than start. Open bounds participate in overlap checks. All validation uses the stored event timezone. Nonexistent DST times fail; ambiguous fall-back times use the first occurrence.

`POST /api/events/{id}/pricing-preview` accepts `{"page": <complete editable definition>, "at": "2026-10-02T09:00"}` within the 500 KB limit and normal Origin rules. Empty/missing `at` uses server current time. The response contains `timezone`, offset-bearing `at`, `currency` and a `regtypes` map keyed by type ID. Each result has `status` (`scheduled`, `default`, `unavailable`), `rate_id`, `name`, `price_minor` (null if unavailable), `start`, `end` and an explanation where applicable. No draft or answer is saved by this operation. Invalid definitions/times return 400; missing event 404; database failures 503.

## Images and appearance

Upload requests contain raw image bytes (not JSON or multipart), with Content-Length of 1–8,388,608 bytes. The content is verified independently of the claimed Content-Type. Static PNG/JPEG/WebP only; 6000 px per side and 16 MP maximum. The server normalizes to metadata-free PNG within 2560×2560 and caps output at 16 MB. Response: `{"id":"<uuid>","kind":"logo","url":"/api/events/<event-id>/assets/<asset-id>"}`. Invalid images/size/ID return 400; absent event 404; storage failures 503. The normal write Origin rule applies. Uploading persists an asset immediately, but does not update the saved page selection.

Page payload `appearance` is optional. It accepts `logo_asset_id` and `background_asset_id` as UUID strings/null and `background_fade` as integer 0–100, default 80. Saving an asset belonging to another event, a missing asset, or the wrong kind returns 400 without changing the saved page. To remove a selection, save null; no DELETE endpoint exists. Old/replaced files are retained.

Asset GET requires matching event ownership, returns `image/png`, `X-Content-Type-Options: nosniff` and `Cache-Control: private, max-age=3600`. Unknown/mismatched assets return 404. Files are immutable and UUID-named; uploaded names are never paths. The existing local-only authentication limitation still applies.

## Demographics, membership and address additions (September 30, 2026)

`GET/PUT /api/events/{id}/demographics` reads/saves `{title,intro,questions}`. Stable question and option IDs are required. Each question includes `type`, `label`, `help`, `required`, `options`, `visible_to` (null/all or a nonempty RegType ID array), and `conditions:{mode:"all"|"any",rules:[{question_id,operator,value}]}`. Earlier references only; stale RegTypes/options and incompatible rules are rejected. Max 500 KB request.

`POST /api/events/{id}/demographics-preview` accepts `{page,answers,regtype_id,check,registration_page?}` and returns `{visible_ids,effective_answers,errors}`. Optional registration_page allows a detached preview to use validated unsaved RegTypes. The endpoint writes nothing. The organizer Demographics page contains no answer form; this endpoint serves the separate attendee preview.

`GET/PUT /api/events/{id}/membership` reads/saves configuration and returns import count/revision/time, never the full roster. Config is `{enabled,source:"csv"|"api",policy:"required"|"pending",regtype_ids,api:{endpoint,credential_env,mapping}}`. See MEMBERSHIP.md.

Membership POST suffixes:

| Suffix | Input and result |
| --- | --- |
| `/import-preview` | `{csv,mapping}` → validated counts, masked sample, digest, current revision |
| `/import` | Same + `{digest,revision}` → atomic replacement metadata |
| `/lookup` | `{member_id?,email?,regtype_id,config?}` → verification/pending outcome, reason, continuation and pricing treatment; no identity/roster returned |
| `/test` | `{member_id?,email?,config}` → adapter connection-shape result |

Membership HTTP body max 2.5 MB; CSV text max 2 MB/10,000 rows. Validation failure leaves saved values unchanged. Optional config is only for unsaved organizer preview.

`GET /api/address-config` returns provider readiness without a key. `POST /api/address-suggestions` takes `{query}` (3–300 characters, max 2 KB HTTP body) and returns status/message/sanitized suggestions. Unconfigured and unavailable cases return an empty list for manual fallback. Query bodies are not logged. The key never reaches the browser.

Event POST/PUT now accepts optional `address:{line1,line2,city,region,postal,country}` (each string ≤500 characters), retaining legacy location. The UI advances to Registration page only after a successful event POST/PUT.

`DELETE /api/events/{id}` requires `{confirm_name:"exact saved event name"}`. A mismatch returns 400, missing event 404. Success cascades related database rows, deletes event-owned generated image files where possible, and returns `{deleted,retained_image_files}`. Unlink failure does not undo committed database deletion; retained files are orphaned/inaccessible via the app and can be cleaned during maintenance. No other event is changed.

All HTTP requests require Host matching localhost/127.0.0.1 and the current server port, preventing DNS-rebinding access. Mutation endpoints reject foreign Origin headers. This remains a local unauthenticated tool, not an Internet service.
