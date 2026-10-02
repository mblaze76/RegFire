#!/usr/bin/env python3
"""Interactive local setup. Never pass passwords as command-line arguments."""
import getpass, json, os, secrets, sys
import psycopg
from psycopg import sql
from database import CONFIG, Store


def main():
    if CONFIG.exists():
        try:
            with Store().connect() as conn:
                conn.execute('SELECT 1')
            print('Existing Regfire connection verified; settings unchanged.')
            return
        except Exception:
            raise SystemExit('Existing settings could not connect. They were preserved; do not replace them without checking the database.')
    if not sys.stdin.isatty():
        raise SystemExit('Run this setup directly in Terminal so your password can be entered privately.')
    print('Regfire local PostgreSQL setup. No password is displayed or sent to chat.')
    admin = input('PostgreSQL administrator username [postgres]: ').strip() or 'postgres'
    port = int(input('Local PostgreSQL port [5432]: ').strip() or '5432')
    dbname = input('New database name [regfire_local]: ').strip() or 'regfire_local'
    role = input('New app account name [regfire_app]: ').strip() or 'regfire_app'
    password = getpass.getpass('PostgreSQL administrator password: ')
    try:
        conn = psycopg.connect(host='127.0.0.1', port=port, user=admin, dbname='postgres', password=password, connect_timeout=5, autocommit=True)
    except psycopg.Error:
        raise SystemExit('Could not authenticate to local PostgreSQL. No changes were made. Check the username, password and port, then retry.')
    password = None
    with conn:
        if conn.execute('SELECT 1 FROM pg_database WHERE datname=%s', (dbname,)).fetchone() or conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone():
            raise SystemExit('That database or account already exists. Nothing was changed. Run setup again and choose unused names.')
        generated = secrets.token_urlsafe(36)
        try:
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE').format(sql.Identifier(role), sql.Literal(generated)))
            conn.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(dbname), sql.Identifier(role)))
        except psycopg.Error:
            raise SystemExit('PostgreSQL could not create the database/account. Setup stopped; check administrator privileges. A newly created account may remain; choose unused names when retrying.')
    config = dict(host='127.0.0.1', port=port, user=role, dbname=dbname, password=generated)
    CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump(config, file)
    try:
        Store().initialize()
    except psycopg.Error:
        raise SystemExit('Connection settings were saved privately, but schema setup failed. The database and settings were preserved.')
    print('Regfire PostgreSQL is configured. The administrator password was not saved.')
    print('Next: .venv/bin/python migrate_sqlite.py')

if __name__ == '__main__': main()
