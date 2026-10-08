# Regfire — local PostgreSQL edition

Create, list and edit events and their organizer registration-page drafts. The app runs on this Mac; nothing is deployed to cloud.


## Documentation index

- [Demographics setup](docs/DEMOGRAPHICS.md): organizer-only questions, shared RegTypes and branching.
- [Membership](docs/MEMBERSHIP.md): CSV imports, API adapter, verification and pending policies.
- [Separate live preview](docs/LIVE_PREVIEW.md): unsaved edits, second monitor, full-screen control.
- [Address suggestions](docs/ADDRESS_LOOKUP.md): provider configuration and manual fallback.

- [Registration-page builder guide](docs/REGISTRATION_BUILDER.md): RegTypes, dated prices, field dragging, client images/fade, conditional questions and preview.

- [Architecture and source map](docs/ARCHITECTURE.md): components, data flow, implemented behavior and deferred work.
- [Database schema and migration](docs/DATABASE.md): table, JSON fields, keys, constraints, indexes and import rules.
- [HTTP API and validation](docs/API.md): endpoints, request/response behavior and limitations.
- [Operations, backup and recovery](docs/OPERATIONS.md): install, configure, run, stop, back up, restore and troubleshoot.
- [Tests and verified results](docs/TESTING.md): 49 passing checks, browser coverage and verification limits.

## Launch the configured app

The PostgreSQL setup and initial SQLite migration are complete on this Mac. For normal use, run:

```sh
cd /Users/mikeblaze/Documents/Codex/2026-09-29/regfire-event-creation/outputs/regfire
.venv/bin/python server.py
```

Open [Regfire](http://127.0.0.1:8765). Keep Terminal running; Control-C stops it. Do not repeat setup or migration for normal launches. The sections below cover a fresh installation or recovery.

## One-time connection setup

PostgreSQL 18 was verified accepting connections at `127.0.0.1:5432`. It requires authentication. Run the following in your own Terminal:

```sh
cd /Users/mikeblaze/Documents/Codex/2026-09-29/regfire-event-creation/outputs/regfire
.venv/bin/python setup_postgres.py
```

Use the administrator username and password from your PostgreSQL installation. Press Enter to accept each default if appropriate. The password prompt hides what you type. Do not paste the password into chat.

The setup creates a separate `regfire_local` database and a restricted `regfire_app` login. It refuses to overwrite an existing database or account; choose unused names if a collision is reported. The administrator password is never saved. A generated app password is stored in `.local/postgres.json` with owner-only access. Do not share that file or commit it to source control.

If setup reports authentication failure, verify the installer password and administrator username. If setup reports an existing configuration failure, preserve `.local/postgres.json` and check that PostgreSQL is running; deleting it does not reset PostgreSQL.

## Migrate the original drafts, then launch

Stop any earlier Regfire server with Control-C before migrating so no new SQLite edits can occur.

```sh
.venv/bin/python migrate_sqlite.py
.venv/bin/python server.py
```

Open http://127.0.0.1:8765. Keep Terminal running. Press Control-C to stop. For subsequent launches, run just `.venv/bin/python server.py` from this folder. If the port is occupied, stop the old server or use `--port 8766` and open http://127.0.0.1:8766.

The original SQLite database is preserved at `data/regfire.sqlite3`. Before migration, a consistent backup is created in `backups/`. Migration retains IDs and timestamps, skips identical existing drafts, and rolls back the complete import if an existing PostgreSQL record differs. It never overwrites a PostgreSQL draft. The initial inspected SQLite database contained zero drafts.

After migration, new saves go only to PostgreSQL: event details in `regfire.events`, and registration-page definitions in `regfire.registration_pages`. The builder table is added automatically on startup through an additive migration; existing events are preserved. The old SQLite file is a recovery copy, not a current backup. Back up the PostgreSQL database with PostgreSQL's backup tools when you begin storing important records.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Integration tests require the private connection settings. Each creates a randomly named test schema and removes only that schema afterward. Tests cover event and page creation/editing, exact RegType prices, conditional-field references, event isolation, draft ordering, validation, app restart persistence, missing-event requests, cross-origin rejection and safe schema/data migration. When configuration is absent, integration checks are explicitly skipped; that is not a PostgreSQL test pass.

## Reinstall dependencies if moving this folder

Requires Python 3.10+ and a running local PostgreSQL installation. On this Mac Python 3.13 is available.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Scope

This is a local single-user MVP. There is no login, cloud sync, public event page, live attendee submission, email delivery, payment processing or badge printing. Organizer page definitions, dated RegType pricing, field dragging, event-specific logos/backgrounds, fade and conditional-field preview are implemented. Image files are stored in `uploads/`; back them up with PostgreSQL. The server binds to `127.0.0.1` only. Two editors use last-save-wins behavior. Save changes explicitly with **Save draft**.

Times are local wall-clock values with an IANA timezone. Nonexistent daylight-saving times are rejected; the first occurrence of a repeated fall-back hour is used. Venue/link values are retained when switching event format. Optional browser tools expose only a read-only draft list.

## Sign-in and product administration

See [local sign-in and access administration](docs/ACCESS_ADMIN.md) for private owner setup, user/product grants, session security and shared-workspace limitations. The initial owner is reserved privately; no password is preset. Restart the updated local server before setup. Public client hosting and tenant isolation are not implemented.

### Attendee details, categories, and membership

Website setup contains the shared color selector for **Attendee details header font color**, promo-code configuration, and the existing flow-scoped Membership setup. Setup sections and individual category/field cards expand from their summaries; shortcuts open their section, and invalid fields reveal their containing cards. Automatic header color remains available for legacy drafts.

Registration categories render as responsive radio cards with the effective dated rate returned by the pricing service. Nested choices retain their parent category's rate. The deepest selected explicit **Use membership lookup** checkbox controls the existing attendee-field check. Unchecked skips the provider; checked uses the configured membership source and mapped attendee field when membership is enabled. Existing records initially retain their saved membership policy (mixed checkbox); choosing checked/unchecked replaces that inherited behavior. Missing nested choices must be completed before eligibility is checked.

### LinkedIn attendee profile autofill (provider configuration required)

The **Fill in with LinkedIn** button imports an attendee's own first name, last name, and available email through LinkedIn's OpenID Connect consent flow. It fills only empty matching fields and leaves email confirmation, SMS consent, membership verification, and manual entry intact. LinkedIn's standard permissions do not provide employer, job title, phone, or mailing address. This feature does not sign the person into RegFire or certify membership/identity.

Install `requirements.txt`, obtain approval for LinkedIn's **Sign In with LinkedIn using OpenID Connect** product in an app you control, and supply these server environment variables through your private launch configuration:

- `REGFIRE_LINKEDIN_CLIENT_ID`
- `REGFIRE_LINKEDIN_CLIENT_SECRET`
- `REGFIRE_LINKEDIN_REDIRECT_URI`: the exact registered callback, e.g. `http://127.0.0.1:8766/api/linkedin/callback` for this local workspace.

The callback must match the browser's local origin exactly; `localhost` and `127.0.0.1` are different origins. Restart the server after configuration. This repository's existing local-only host/access restrictions remain in force; public attendee deployment is separate work. The import button is unavailable until configuration exists. No provider credentials or approvals are created by the feature.

The server binds one-use, ten-minute authorization state to an HttpOnly browser cookie and validates the ID token signature, issuer, audience, expiration, and nonce before retrieving the matching UserInfo subject. Tokens and profiles remain transient; callback codes are excluded from request logs. Starting import retains existing RegFire preview access requirements. Tests use synthetic provider responses, not a live LinkedIn account. A real consent/permission round trip still needs to be verified after configuration.

Official reference: https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2
