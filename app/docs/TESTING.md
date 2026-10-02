# Verification record and test guide

## Original event-editor verification

On September 29, 2026 (America/New_York), all **seven tests passed with no skips** against local PostgreSQL 18 using Python 3.13 and Psycopg 3.3.6. The run took approximately 3.2 seconds. Tests used random `regfire_test_<uuid>` schemas, not the app's `regfire` schema. Test schemas were removed afterward.

| Test | Evidence |
| --- | --- |
| Create/edit/reload/app restart | POST creates a draft, GET lists it, PUT retains identity and changes values; a new HTTP server and Store read the same PostgreSQL row, also checked directly with SQL |
| Invalid save | End before start returns 400 and inserts no rows |
| Missing edit | PUT for absent UUID returns 404 and inserts no rows |
| Cross-origin write | Foreign Origin returns 403 |
| Migration backup/repeat/conflict | Fixture imports, backup retains source body, repeating import adds zero, conflicting PostgreSQL edit is preserved |
| Invalid fields | Empty name, unknown timezone, malformed email, disallowed URL, nonexistent daylight-saving time and end-before-start are rejected |
| Minimal draft | Name plus timezone and format are accepted without other details |

The persistence test restarts the **application HTTP server and Store**, not the PostgreSQL service or Mac. Database-service restart, power-loss recovery, load testing and PostgreSQL dump/restore rehearsal have not been performed. The documented backup/restore commands are procedures, not claimed completed tests.

The real SQLite migration completed with zero source rows and zero inserts, preserving the source and timestamped backups. Therefore fixture-based migration testing supplies the nonempty migration evidence.

Browser QA previously verified creating, saving, reloading and editing an online draft, the stored link, desktop appearance and a narrow layout without horizontal overflow. That browser interaction run was on the original SQLite version; the PostgreSQL transition retained the same UI and was verified through HTTP integration tests. The final local page and list endpoint were checked after PostgreSQL launch. The optional browser read-only draft-list tool was exercised in the earlier browser run; no create/edit browser tool exists.

For this documentation pass, the live PostgreSQL catalog was queried to confirm the single application table, columns, NOT NULL constraints and primary-key index. The live list endpoint was available with zero event drafts. No user records were modified for documentation.

## Run checks

From the Regfire source folder:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Run setup first if connection settings do not exist. Without settings, non-database checks run and PostgreSQL integration checks explicitly skip. A skip is not evidence of PostgreSQL functionality. With settings present but an unavailable server, integration tests fail rather than silently using SQLite.

Tests create/drop their own schemas in the configured database. They do not require administrator credentials because the Regfire account owns its database. An interrupted run may leave a `regfire_test_...` schema; inspect it before removing it and never remove `regfire` as test cleanup.

## Manual regression checklist

1. Start the app; confirm saved events load.
2. Create a uniquely named disposable test draft and save it.
3. Reload, reopen it, edit its details and save again.
4. Enter an end time before the start; confirm rejection and preserved form input.
5. Switch between online and in-person; verify retained field values.
6. Restart the app, reopen the saved draft and verify its values.
7. At desktop and mobile widths, confirm controls are readable and no horizontal overflow appears.

Use disposable test drafts for manual checks. The current Delete event action can remove them after an event-name confirmation.

## Registration-builder verification — September 29, 2026

After the builder was added, **all 13 automated tests passed, no skips**, in about 6.1 seconds against local PostgreSQL. This includes the seven original checks plus:

- Page currency, title, field and RegType definition validation, exact integer prices and rejected negative/floating/boolean/out-of-range prices.
- Stable/unique field IDs, option validation and rejection of empty, duplicate or stale RegType references.
- Per-event page save/edit, field removal/order, RegType rename/order, price preservation, isolation from a second event and persistence after app-server/Store restart.
- Atomic rejection of stale visibility references and invalid prices, preserving the previous saved page.
- Missing-event reads/writes and cross-origin rejection for pages.
- Repeated additive schema initialization preserving events and creating the event foreign key.

Browser checks against the PostgreSQL version verified adding/editing/reordering fields, adding/reordering/removing RegTypes, field removal confirmation, saving/reopening the page after reload, and USD 125.50 price display. A Speaker-only required choice appeared for Speaker and blocked a preview check when unanswered; it was absent for Attendee and did not block a complete Attendee preview. International-format phone input was accepted. Required address components were checked with line 2 remaining optional. Switching prices with fractional amounts to JPY was rejected, and returning to USD preserved the values. Removing a referenced RegType was blocked with an actionable message.

The builder and preview were inspected at desktop and narrow mobile widths; no horizontal overflow was found. Test data was disposable and is not an actual event or attendee registration. Backend restart tests restart the app server, not PostgreSQL itself. Payment processing, real attendee submission, browser matrix/load tests and database-service restart remain outside the verified scope.

## Rates, dragging and branding — September 29, 2026

**All 26 automated tests passed with no skips** in approximately 10.8 seconds after these enhancements. Coverage includes the prior 13 checks, six rate tests (legacy default, exact adjacent boundaries, gaps/expiry/default, overlap/reversed/open windows, event timezone/DST and invalid prices/times), two pricing integration checks (save/restart/legacy behavior and timezone-change rollback), three content-validation tests and two upload/persistence/isolation integration tests.

Uploads were tested for actual-content verification, SVG/invalid content/animation rejection, dimensions/size limits, metadata removal and aspect-preserving normalization. Integration tests verify upload/read, replace/remove selection, fade persistence across app restart, immutable prior files and cross-event rejection. They use temporary upload directories and disposable test schemas.

Browser QA verified Early bird to Standard switching exactly at a shared boundary, no-active-rate display at expiry with fallback disabled, and the existing default policy. Real pointer dragging moved Email before Full name; preview order changed and persisted after save/reload with the same field definitions. Show-logo and background uploads completed, replacement retained contained aspect ratio, fade changed only the background opacity from 1 to 0, and 80% fade persisted. Removing both selections survived save/reload. The sample images and event used for QA were disposable; the user's demo page is preserved. Physical-device touch dragging and production image-load/performance testing were not performed; up/down controls remain available.

These remain draft/pricing previews, not payments or attendee submissions. Pricing is evaluated server-side on a debounced request and current-time display refreshes at minute boundaries while visible. Full PostgreSQL-service restart and paired image/database disaster-recovery rehearsal have not been performed.

## Current verification — September 30, 2026

**49 tests passed, no skips**, in approximately 16.4 seconds on the configured local PostgreSQL database. Random disposable test schemas were removed. Coverage now includes nested branching, all/any rules, stable IDs/options, RegType visibility, hidden-required and hidden-answer semantics, invalid references/order, membership import rejection and stale replacement, event isolation/restart, timezone expiration, verified/pending/unavailable policies, local API response fixtures, SSRF restrictions, HTTP Host guard, unsaved RegTypes in detached preview, structured-address preservation, optional-provider/manual fallback, and event deletion cascades. Earlier rate/image/event checks remain in the suite.

Browser checks: authored and saved a shared Attendee/Speaker yes/no question, configured a required dropdown follow-up, duplicated/reordered/removed a question, verified dependency deletion and invalid-order guards, and reloaded saved definitions. After the clarified scope, the Demographics setup contains zero attendee answer forms; attendee branch checks occur in the separate preview. At 390px width, the setup controls remained usable without horizontal overflow.

Membership browser checks used synthetic records only: API fixture connection test, verified result, pending-on-unavailable result, CSV mapping/validation/masked preview/confirmed replacement, saved list reload and a verified imported match. No live provider was contacted.

Two-window checks verified unsaved title and price changes, field reordering, RegType switching and required follow-up behavior; hidden answers reset when changing to Staff; switching the organizer to a different event paused the old preview without cross-event data. The browser's popup behavior required the explicit new-tab fallback link. The final browser check successfully entered Full screen (button changed to Exit full screen) and exited back to the normal window. It is not claimed to move a window across physical monitors.

Address browser checks used a separate synthetic server: event suggestion selection populated components, Suite 42 persisted, registration address selection retained Apt 7. Both a newly created draft and an edited event advanced to Registration page only after successful save; reversed end time stayed on Event details with the entered value and server validation error. Deletion cancellation retained the form; confirmed deletion removed only the disposable QA event and returned to a new draft. The preserved demo event was not deleted or overwritten.

No external address or membership provider, real credentials, public registration, payments, real review queue, cloud publishing, database-service restart, load test or physical two-monitor movement was verified.

## Demographics preview and dropdown correction

The latest user clarification adds an embedded, separately labeled Demographics website preview. It reuses the same renderer and event/editor channel as the separate window. Browser checks verified an unsaved Single choice → Dropdown change appearing in the embedded preview, Workshops → Event technology revealing both levels of follow-up, and a Demographics new-window link containing `view=demographics` with no registration/contact form displayed. Registration's launch path remains registration mode.

The apparent non-working Question type dropdown was a blanket guard against changing any question referenced by a rule. Compatible types now preserve the existing rule and choice IDs. Incompatible changes explicitly confirm required rule resets and removal of choices; cancel was verified to preserve the original selection. On a disposable event, changed question type, any-rule logic, comparison, answer choice and RegType assignment were saved; reload retained Dropdown/any/not-equals/Option 2. A confirmed switch to Number reset the dependent comparison to Is answered and saved successfully. Only that disposable event was deleted after testing. The user's saved demo was unchanged.

## Preview choice styling

Preview checkboxes/radios use shared 20px controls in 48px minimum clickable label rows, with Regfire warm checked backgrounds and a visible keyboard-focus outline. Styles apply to embedded Demographics, separate live previews and registration preview choice rows. Browser checks verified simultaneous checkbox selections, Space-key toggling, dependent-question visibility after unchecking, and consistent embedded dimensions. At 390px viewport width, content did not overflow horizontally. Native input semantics are retained, with a forced-colors native-control fallback. No saved question definitions changed during styling checks.
