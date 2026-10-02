# Local operations, backup and recovery

## Requirements and installation

Verified environment: macOS, Python 3.13, PostgreSQL 18 from the official installer, Psycopg 3.3.6 and Pillow 12.3.0. The pinned Psycopg release requires Python 3.10 or newer; Python 3.13 is the tested choice. This Mac has system timezone data. There is no Node/frontend installation or compilation step.

From the source folder, installation on a fresh copy is:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python setup_postgres.py
```

The current installation is already configured; do not recreate its database. Startup now also applies the additive registration-page SQL migration. Keep the `migrations/` folder with the source. No new credentials or setup action is needed for the builder. Setup runs in Terminal, prompts privately for the PostgreSQL administrator password, and defaults to local port 5432, database `regfire_local` and app login `regfire_app`. It refuses existing database/account names. Existing settings are verified and left unchanged. A partial account/database creation failure may leave the new account behind; inspect before retrying with unused names.

The administrator password is not saved. Setup generates a separate app password and stores connection fields `host`, `port`, `user`, `dbname`, `password` in `.local/postgres.json`. No credential values are included in these docs. Settings are loaded relative to the source file, not the current directory. The loader rejects group/other permissions; the expected file mode is 600. Setup creates the parent with mode 700. Filesystem owner/admin access can still read this plaintext local credential. There is no environment-variable or connection-string override in the app.

## Start, stop and restart

```sh
cd /Users/mikeblaze/Documents/Codex/2026-09-29/regfire-event-creation/outputs/regfire
.venv/bin/python server.py
```

Open [Regfire](http://127.0.0.1:8765). Keep the process running; Control-C stops it. Restart with the same command. PostgreSQL runs independently and must also be available. The app has no automatic login-time startup. Use `--port 8766` if you intentionally need an alternate HTTP port; this does not change PostgreSQL's port.

Initial SQLite migration was already completed. Do not run it on every launch. For an unmigrated copy, stop the legacy app, configure PostgreSQL, then run `.venv/bin/python migrate_sqlite.py` once before starting the new app. A different source can be passed with `--source /absolute/path/to/regfire.sqlite3`.

## Back up active PostgreSQL data

The original SQLite file is not a backup of new saves. The following commands use PostgreSQL 18's installed tools and prompt for the administrator password locally. Substitute the actual administrator username if it differs. No password is placed in shell history, arguments or this document.

```sh
mkdir -p backups
chmod 700 backups
umask 077
/Library/PostgreSQL/18/bin/pg_dump -h 127.0.0.1 -p 5432 -U postgres -W -d regfire_local --format=custom --no-owner --no-acl --file="backups/regfire-$(date +%Y%m%d-%H%M%S).dump"
```

A successful exit is required; do not rely only on the existence of an output file. `pg_dump` takes a consistent database snapshot while the app is running, but later saves are naturally not included. Keep backup copies on a separate protected location if needed. The custom archive contains event, registration-page and asset-metadata tables, but not image binaries or PostgreSQL role passwords. Pair it with the uploads directory as described below. Store the source and dependencies separately. Preserve `.local/postgres.json` privately if retaining the same app account; do not attach it to documentation or share it.

Inspect archive structure with `pg_restore --list` using the full executable path. This checks readability, not full recovery; a restore rehearsal is stronger evidence.

## Restore without overwriting the live database

This is a recovery procedure, not an action already performed. Choose an unused database name. Do not use `--clean` against the live database. Replace the archive filename below with the real backup filename.

```sh
/Library/PostgreSQL/18/bin/createdb -h 127.0.0.1 -p 5432 -U postgres -W --owner=regfire_app regfire_restore_check
/Library/PostgreSQL/18/bin/pg_restore -h 127.0.0.1 -p 5432 -U postgres -W --dbname=regfire_restore_check --role=regfire_app --no-owner --no-acl --single-transaction --exit-on-error backups/CHOSEN_BACKUP.dump
/Library/PostgreSQL/18/bin/psql -X -h 127.0.0.1 -p 5432 -U postgres -W -d regfire_restore_check -c 'SELECT count(*) AS events FROM regfire.events; SELECT count(*) AS registration_pages FROM regfire.registration_pages;'
```

These commands assume the existing `regfire_app` role remains available. On a replacement machine, create a new local Regfire account through setup first, and use its name as owner/role. The administrator must be permitted to create the database and set that role. Restore failures leave the original database untouched; investigate the new restore target before retrying.

After successful restore, compare counts and representative records with the expected backup, not necessarily the latest live data. To test the restored data in Regfire, stop the app, preserve a private copy of `.local/postgres.json`, and change **only** its `dbname` value to the restored database using a local editor. Keep permissions at 600. Start the app and verify the list and a test create/edit. Keep the original database intact until recovery is accepted. To revert, stop the app, restore the previous private settings and restart. Do not use setup to overwrite an existing database.

## Recover legacy SQLite data

`backups/regfire-before-postgres-*.sqlite3` files are consistent copies of the old store. Leave the original and backups unchanged. To import one, use `migrate_sqlite.py --source /absolute/path/to/backup.sqlite3`; this creates another backup and applies the no-overwrite rules. An ID conflict requires manual reconciliation; the tool intentionally will not discard a newer PostgreSQL edit. The current server cannot run directly against SQLite.

## Troubleshooting

| Symptom | Check/action |
| --- | --- |
| Browser cannot connect | Confirm the server Terminal is still running and use the printed HTTP port |
| Address already in use | Stop the known old app or select another HTTP port; do not terminate unrelated processes |
| PostgreSQL unavailable | Run `/Library/PostgreSQL/18/bin/pg_isready -h 127.0.0.1 -p 5432`; check the installation's service controls if not accepting |
| Configuration unavailable | Confirm `.local/postgres.json` exists; run setup only for initial configuration |
| Permissions rejected | Run `chmod 600 .local/postgres.json`; do not print its contents |
| Save/list failure | Keep unsaved form open, restore database availability, then retry; a lost POST response may require checking for an already-created draft |
| Migration conflict | Preserve source, backup and current database; compare the conflicting records before deciding which version to retain |
| Thirteen tests skipped | Connection file is absent; integration coverage was not executed |

The app logs HTTP request paths/statuses, not request bodies or credentials. Its startup/error messages are intentionally generic. PostgreSQL permissions, backup scheduling, monitoring and disaster-recovery rehearsals remain local operator responsibilities; cloud migration is deferred.

## Builder upgrades and recovery

Back up PostgreSQL before schema upgrades. The first builder migration is `migrations/001_registration_pages.sql`, executed by `Store.initialize()` in a transaction. It adds the per-event page table with a foreign key; it neither deletes nor modifies existing event rows. Repeated application leaves data unchanged. There is no migration-history runner or automatic reverse migration. To roll back code for diagnosis, preserve the new table and backup rather than dropping it; older event-only code ignores it.

For archives made before the builder existed, the restore count query for `registration_pages` will fail because that table was absent. Start the new app against the restored database to create the empty table, then check counts. Such an old archive cannot recover newer page drafts. For current archives, verify both tables and open each important event's Registration page after restore. Prices and conditions are part of page JSON; compare them along with field order. Preview answers are intentionally not recoverable because they are never saved.

## Back up uploaded branding with the database

A PostgreSQL-only dump is no longer a complete backup once images have been uploaded. For a matched recovery snapshot, stop Regfire with Control-C to prevent writes/uploads, leave PostgreSQL running, and create a protected snapshot directory. These commands use a local administrator password prompt; no password belongs in the command or documentation.

```sh
umask 077
regfire_snapshot="backups/snapshot-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$regfire_snapshot"
/Library/PostgreSQL/18/bin/pg_dump -h 127.0.0.1 -p 5432 -U postgres -W -d regfire_local --format=custom --no-owner --no-acl --file="$regfire_snapshot/database.dump"
```

Only after pg_dump exits successfully, copy the current `uploads/` directory into that same snapshot (`cp -R uploads "$regfire_snapshot/uploads"`). If no uploads directory exists, record that there were no files rather than inventing one. Then restart the app. Keep the SQL archive and files together. Source, migrations and requirements also need to be retained; connection settings remain private.

Restore the database into an unused database as already described. Before pointing Regfire at it, stop the app, preserve the existing uploads directory in a separate recovery folder, and copy the snapshot's uploads back to the app's `uploads/` path. Do not overwrite the original files. Change only the private database name setting, keeping its permissions 600, then start and verify page counts, prices, image rendering and fade. To revert, restore both the prior database setting and its matching uploads directory. Archives made before image support need no files and startup adds an empty asset table.

Removed/replaced uploads are retained and not automatically pruned. This makes save/discard safe but consumes disk space. There is no cleanup tool in this MVP. Do not delete a file merely because it is not visible in the current preview; it may be referenced by another saved page or recovery snapshot. Event ownership is checked by the app, and shell access to the private uploads folder remains an operator capability.

## Optional providers and event deletion

See ADDRESS_LOOKUP.md for Geoapify environment settings and MEMBERSHIP.md for server-only bearer credentials and the exact supported API shape. Do not put credential values in the browser, repository, screenshots or chat. Restart the Python server after changing its environment. Normal address lookup remains unconfigured; fixture mode is for testing only.

Database dumps now include demographics and membership imports; treat them as private member data. Pair database backups with uploaded images and protect both. The preserved pre-Demographics dump is `backups/regfire-before-demographics-20260930T040132Z.dump`. It is a point-in-time backup, not a replacement for later user edits.

Delete event is available on Event details for a saved event. Its confirmation names the event and explains all related data removal. Cancel does not change the draft or unsaved form. Successful deletion returns to a valid new-event form and refreshes the list. Restore from a suitable backup if recovery is required; no in-app undo exists. Failed image-file cleanup can leave orphaned files after deletion, but they are no longer served by any asset metadata route.
