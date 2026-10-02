# PostgreSQL schema and migration

Verified against the running local database on September 29, 2026 (America/New_York). Database: `regfire_local`; login/owner created by setup: `regfire_app`; application schema: `regfire`.

## Current schema

There are **six application tables**: `events`, `registration_pages`, `registration_assets`, `demographics_pages`, `membership_settings` and `membership_imports`, all in schema `regfire`. Each event may have zero or one registration-page draft. `registration_pages.event_id` references `events.id` with ON DELETE CASCADE. The named-confirmation event DELETE endpoint cascades related records. There are no attendee-response, payment, join, sequence, trigger or migration-history tables created by this app.

```sql
CREATE SCHEMA IF NOT EXISTS regfire;
CREATE TABLE IF NOT EXISTS regfire.events (
    id UUID PRIMARY KEY,
    body JSONB NOT NULL,
    updated TIMESTAMPTZ NOT NULL
);
```

| Column | Type | Null/default | Meaning |
| --- | --- | --- | --- |
| `id` | `uuid` | NOT NULL; no default | Event identity, generated as UUID v4 in Python for new drafts |
| `body` | `jsonb` | NOT NULL; no default | Complete normalized event object returned by the API |
| `updated` | `timestamp with time zone` | NOT NULL; no default | Save timestamp supplied by Python; used for list ordering |

For the events table, the primary-key constraint is `events_pkey`. It creates its sole index: a unique B-tree on `id`. PostgreSQL 18 also exposes named NOT NULL constraints `events_id_not_null`, `events_body_not_null` and `events_updated_not_null`. There is no index on `updated` or JSON fields, so large lists may require a scan and sort.

There are no JSON shape checks, enum constraints or database-side checks that `body.id` equals `id` or `body.updated` equals `updated`. The application maintains those values. Direct SQL can bypass application validation.

## JSON body

Every normal save includes the following string-valued properties. Optional missing fields normalize to empty strings; whitespace at either end is removed.

| Property | Meaning |
| --- | --- |
| `name` | Required nonblank event name |
| `start`, `end` | Optional wall-clock times in `YYYY-MM-DDTHH:MM` form |
| `timezone` | Required IANA timezone identifier |
| `format` | Required `in_person` or `online` |
| `venue`, `location` | Optional venue and address/location |
| `url` | Optional HTTP/HTTPS online-event link |
| `description` | Optional description |
| `organizer`, `email` | Optional contact name/organization and email |
| `id` | String form of the table UUID |
| `status` | Always `draft` for API writes |
| `created` | UTC ISO timestamp generated on first save; preserved on edits |
| `updated` | UTC ISO timestamp generated on every save |

Event times are not database timestamp columns and are not automatically converted for display. They are stored with their timezone. Validation compares their UTC equivalents; nonexistent spring-forward times are rejected and repeated fall-back times use the first occurrence. Metadata timestamps are separate UTC save times.

See [API and validation](API.md) for exact accepted values and limits.

## Initialization and future schema changes

`Store.initialize()` executes the event DDL above and the ordered SQL files under `migrations/` during server startup, first-time setup and SQLite migration. The SQL template safely quotes `{schema}` so tests use their own schema. All initialization/migration statements run in one transaction and are idempotent for an already matching schema. The page migration only adds a table; it does not rewrite event rows. This is **not a versioned migration system**: `IF NOT EXISTS` neither upgrades nor verifies an incompatible existing table. Future schema changes need explicit, backed-up migrations before deployment; no automatic alteration exists now.

Each save runs in a transaction. An edit selects its current record `FOR UPDATE`, preserves `created`, and updates body/timestamp. Missing edits return 404; they do not insert. Creation uses INSERT, not an overwrite-on-conflict operation. Listing selects bodies ordered by `updated DESC, id`.

## Original SQLite migration

The legacy table was `events(id TEXT PRIMARY KEY, body TEXT NOT NULL, updated TEXT NOT NULL)`. It is preserved at `data/regfire.sqlite3`.

Run `migrate_sqlite.py` only after stopping any older SQLite-backed server. The script:

1. Opens the SQLite source read-only and uses SQLite's backup API to create a consistent, timestamped file under `backups/`, with owner-only permissions.
2. Reads rows from that backup and initializes the PostgreSQL schema if needed.
3. Locks the destination table in `SHARE ROW EXCLUSIVE` mode for the import transaction.
4. Inserts missing IDs with original bodies and timestamps; skips identical JSON bodies already present.
5. Rolls back all imported rows if an existing ID has a different body or another import error occurs. Backup and source remain intact.

Identical-body detection does not separately compare the destination's `updated` column. Migration parses JSON but does not rerun current field validation; it is intended for the known legacy draft store. It does not reconcile conflicting edits. Repeating it after PostgreSQL edits can legitimately report a conflict.

The real migration completed with zero source drafts and zero inserts. A separate fixture-based integration test verified import, backup content, repeat import and conflict preservation. SQLite backups do not contain later PostgreSQL saves. Use the [operations guide](OPERATIONS.md) for current backups and restore.

## Registration-page table

```sql
CREATE TABLE IF NOT EXISTS regfire.registration_pages (
    event_id UUID PRIMARY KEY REFERENCES regfire.events(id) ON DELETE CASCADE,
    body JSONB NOT NULL,
    updated TIMESTAMPTZ NOT NULL
);
```

| Column | Type | Constraints/default | Meaning |
| --- | --- | --- | --- |
| `event_id` | UUID | NOT NULL; primary key; foreign key to events; no default | One page per existing event |
| `body` | JSONB | NOT NULL; no default | Complete organizer page definition |
| `updated` | TIMESTAMPTZ | NOT NULL; no default | Last page-save time |

`registration_pages_pkey` is the unique B-tree index on `event_id`. `registration_pages_event_id_fkey` enforces event existence. PostgreSQL 18 exposes the three corresponding NOT NULL constraints. There is no additional index; the primary key supports lookup by event. RegTypes and fields are ordered JSON arrays, not separate tables.

The page body contains `event_id`, `status` (always `draft`), `updated`, `title`, `intro`, `currency`, `regtypes` and `fields`. Each RegType contains stable `id`, editable `name`, nonnegative integer default `price_minor`, boolean `use_default` and a `rates` array. Each rate has stable `id`, `name`, integer `price_minor`, and optional local `start`/`end` strings. Legacy records without the new properties mean `use_default: true` and `rates: []`. Each field contains stable `id`, `label`, `type`, boolean `required`, string-array `options` and `visible_to`: null for all RegTypes, or a nonempty list of current RegType IDs. Array order controls display order. Address structure is fixed in the preview: line1, line2, city, region, postal and country.

JSON shape, unique child IDs/names, price bounds/currency, options and visibility references are application validations, not SQL CHECK constraints. Direct SQL can bypass them. Page saves use a transaction with an event row lock and an upsert. Event-detail saves do not overwrite page definitions. No actual attendee data or payment details are stored by the preview.

A GET with no saved page returns an unsaved starter with `updated: null` and does not insert a row. PUT stores the full normalized definition and UTC save time. RegType removal with stale field references is rejected; rename/reorder preserve IDs. There is no patch/version conflict protocol.

Before this migration, a PostgreSQL custom-format backup was created as `backups/regfire-before-builder-20260930T011852Z.dump`. Application of the additive DDL was checked to leave all existing event rows unchanged. The SQLite import continues to import only event definitions; it does not synthesize saved page rows. Full PostgreSQL dumps now include both tables.

## Assets and appearance

Migration `002_registration_assets.sql` adds the following table without rewriting existing events or pages:

```sql
CREATE TABLE regfire.registration_assets (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES regfire.events(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('logo', 'background')),
    filename TEXT NOT NULL UNIQUE,
    mime TEXT NOT NULL CHECK (mime = 'image/png'),
    byte_size INTEGER NOT NULL CHECK (byte_size > 0),
    created TIMESTAMPTZ NOT NULL
);
CREATE INDEX registration_assets_event_idx ON regfire.registration_assets(event_id);
```

There are no column defaults. UUIDs and created timestamps are supplied by the app. Besides the event index, the primary key and filename uniqueness each create a unique B-tree index. One event may own many immutable image records; the foreign key cascades metadata on direct event deletion but does not delete filesystem files. The app has no event-delete endpoint. Normalized content lives under `uploads/<uuid>.png`, with private file permissions. No uploaded filename or arbitrary filesystem path is accepted from the client.

Page JSON now includes `appearance: {logo_asset_id, background_asset_id, background_fade}`. IDs are UUID strings or null; fade is an integer 0–100, default 80. IDs in JSON are checked for existence, same event and correct kind when saving; these are application validations, not SQL foreign keys from JSON. Old pages default to null assets and fade 80 until next save. Backgrounds and logos are optional.

No SQL change is needed for dated-rate JSON. Reads preserve old records. A save normalizes them into the expanded definition while retaining existing prices, IDs, field settings and ordering. Event and page writes lock the event row to serialize timezone changes with page validation. Reinterpreting invalid rate times under a new event timezone rejects the transaction. Image binaries are never put into the JSON body or database.

The pre-enhancement PostgreSQL backup was `backups/regfire-before-rate-periods-20260930T031735Z.dump`. New full backups must pair the database archive with the upload directory. Rate schedules and appearance selections are included in page JSON; files are separate. No migration-history table or automated reverse migration is introduced.

## Current additions

There are now six application tables: `events`, `registration_pages`, `registration_assets`, `demographics_pages`, `membership_settings`, and `membership_imports`.

Migration 003 adds `demographics_pages(event_id UUID PRIMARY KEY REFERENCES events ON DELETE CASCADE, body JSONB NOT NULL, updated TIMESTAMPTZ NOT NULL)`. Body stores question definitions, stable IDs, option IDs, RegType assignments and rules; no answers.

Migration 004 adds `membership_settings` with the same event/body/updated layout and `membership_imports(event_id UUID PRIMARY KEY REFERENCES events ON DELETE CASCADE, records JSONB NOT NULL, digest TEXT NOT NULL, updated TIMESTAMPTZ NOT NULL)`. Records are normalized member objects, replaced atomically after validation. Credentials are environment-only, not database values. Imported records are not returned through GET endpoints.

The event JSON may include an `address` object with line1, line2, city, region, postal and country. Existing `location` text is preserved; no destructive backfill occurs. Old events without the object load blank optional component controls.

Event row locks serialize related definition writes, imports and deletion. Registration saves validate references from saved demographics and membership. Event deletion cascades all related rows; only generated images owned by that event are selected for filesystem cleanup after commit. Other events and their files remain intact. Backup/restore remains the recovery mechanism; there is no deleted-event trash UI.
