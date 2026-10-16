"""Read-only event Welcome projection for a selected registration flow."""
from psycopg import sql

def model(store, flow, public=False):
    from publication_snapshot import current, load
    from public_attendee import enabled
    with store.connect() as c:
        row=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()),(flow,)).fetchone()
        if not row:raise ValueError('Registration not found.')
        owner=row[0].get('parent_event_id',flow)
        parent=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()),(owner,)).fetchone()
        page=c.execute(sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(sql.Identifier(store.schema,'welcome_pages')),(owner,)).fetchone()
        rows=c.execute(sql.SQL('SELECT id,name FROM {} WHERE event_id=%s AND NOT archived ORDER BY position,id').format(sql.Identifier(store.schema,'registration_flows')),(owner,)).fetchall()
    snap=(current(store,flow) or load(store,flow)) if public else None
    welcome=dict(snap.get('welcome') or {}) if snap else dict(page[0] if page else {})
    event=(snap or {}).get('parent') or (parent[0] if parent else {})
    flows=[]
    for key,name in rows:
        key=str(key)
        if public:
            if not enabled(store,key):continue
            published=load(store,key)
            if published:
                # Labels come from published configuration, not subsequent draft edits.
                button=next((b for b in published.get('welcome',{}).get('buttons',[]) if b.get('flow_id')==key),None)
                name=(button or {}).get('label') or published['event'].get('name') or name
        flows.append(dict(id=key,name=name))
    welcome.setdefault('sponsor_asset_ids',[])
    welcome.setdefault('about','')
    welcome.setdefault('title','Welcome to online registration')
    welcome['buttons']=[dict(flow_id=f['id']) for f in flows]
    return dict(event_id=owner,event_name=event.get('name',''),page=welcome,flows=flows)
