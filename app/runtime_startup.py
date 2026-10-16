"""Separate production startup from privileged schema and owner provisioning."""

def prepare_store(store, deployment):
    if not deployment.secure_cookies:
        store.initialize()
        return
    # Runtime credentials need only read/write access. Schema migration is an
    # explicit operator job, never a side effect of starting a web worker.
    from psycopg import sql
    required = ('events', 'registration_pages', 'registration_flows', 'registration_publications', 'partial_registrations', 'client_intake_previews')
    with store.connect() as connection:
        for table in required:
            connection.execute(sql.SQL('SELECT 1 FROM {} LIMIT 0').format(
                sql.Identifier(store.schema, table)))


def prepare_owner(access, deployment):
    if deployment.secure_cookies:
        if not access.configured():
            raise RuntimeError('Provision the staging owner privately before starting production mode.')
        return
    import owner_setup
    owner_setup.prepare(access)
