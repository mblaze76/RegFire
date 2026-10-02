"""Back up SQLite, then transactionally import without overwriting PostgreSQL rows."""
import argparse, json, sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from psycopg import sql, Error
from psycopg.types.json import Jsonb
from database import ROOT, Store


def migrate(source, store, backup_directory=None):
    if not source.is_file():
        raise RuntimeError('SQLite source not found; nothing was migrated.')
    directory = backup_directory or ROOT / 'backups'
    directory.mkdir(mode=0o700, exist_ok=True)
    backup = directory / ('regfire-before-postgres-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
        with closing(sqlite3.connect(backup)) as copy:
            original.backup(copy)
            rows = copy.execute('SELECT id, body, updated FROM events').fetchall()
    backup.chmod(0o600)
    store.initialize()
    inserted = 0
    with store.connect() as conn:
        # Serialize concurrent migration runs; no partial imports on conflict.
        conn.execute(sql.SQL('LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE').format(store.table()))
        for event_id, body, updated in rows:
            data = json.loads(body)
            old = conn.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()), (event_id,)).fetchone()
            if old:
                if old[0] != data:
                    raise RuntimeError('An existing PostgreSQL draft differs from SQLite. Import rolled back; both originals are preserved.')
                continue
            conn.execute(sql.SQL('INSERT INTO {} (id,body,updated) VALUES(%s,%s,%s)').format(store.table()), (event_id, Jsonb(data), updated))
            inserted += 1
    return len(rows), inserted, backup


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--source', type=Path, default=ROOT / 'data' / 'regfire.sqlite3'); args = parser.parse_args()
    try:
        count, inserted, backup = migrate(args.source.resolve(), Store())
        print(f'Checked {count} SQLite drafts; imported {inserted}. Backup: {backup.name}')
    except (RuntimeError, Error, sqlite3.Error, ValueError):
        raise SystemExit('Migration did not complete. Source data and any backup were preserved. Check local configuration and draft conflicts before retrying.')

if __name__ == '__main__': main()
