"""Bounded transactional outbox worker; never enables providers or retries uncertainty."""
import logging, os, threading
from psycopg import sql
from confirmation_delivery import dispatch, readiness

log = logging.getLogger('regfire.confirmations')

def run_once(store, settings, *, client=None, upload_root=None, limit=20):
    problems = readiness(settings)
    if problems:
        return {'state': 'disabled', 'issues': problems, 'submitted': 0, 'failed': 0}
    table = sql.Identifier(store.schema, 'confirmation_delivery')
    with store.connect() as c:
        ids = [str(r[0]) for r in c.execute(sql.SQL(
            "SELECT order_id FROM {} WHERE status='queued' ORDER BY updated,order_id LIMIT %s"
        ).format(table), (max(1, min(int(limit), 100)),)).fetchall()]
    result = {'state': 'enabled', 'submitted': 0, 'failed': 0}
    for ident in ids:
        try:
            dispatch(store, settings, ident, client, upload_root=upload_root)
            result['submitted'] += 1
        except Exception:
            # dispatch commits submitting before I/O; never release an uncertain
            # claim. Only a still-queued local failure becomes visibly blocked.
            with store.connect() as c:
                c.execute(sql.SQL("UPDATE {} SET status='blocked',updated=now() WHERE order_id=%s AND status='queued'").format(table), (ident,))
            result['failed'] += 1
            log.warning('confirmation_requires_review')
    return result

def start(server, interval=30):
    # Startup must not read provider secrets or create a sender unless the
    # operator explicitly enabled both gates outside synthetic staging.
    if (os.environ.get('REGFIRE_STAGING') == '1' or
        os.environ.get('REGFIRE_CONFIRMATION_EMAIL_LIVE') != '1' or
        os.environ.get('REGFIRE_COMMUNICATIONS_LIVE') != '1'):
        return None
    from communications import settings_for
    settings = settings_for(server)
    stop = threading.Event()
    def loop():
        while not stop.is_set():
            try:
                run_once(server.store, settings, upload_root=getattr(server, 'upload_root', None))
            except Exception:
                log.error('confirmation_worker_unavailable')
            stop.wait(interval)
    thread = threading.Thread(target=loop, name='confirmation-outbox', daemon=True)
    thread.start()
    return stop
