"""Shared event footer with preserved legacy values and explicit conflict resolution."""
from psycopg import sql
from psycopg.types.json import Jsonb
from registration import starter,validate_page
import json


def normalize(footer):
    page=starter(dict(id='footer-validation',name='Footer'))
    page.setdefault('appearance',{})['footer']=footer
    return validate_page(page)['appearance']['footer']


def operation(store,event_id,data=None):
    table=sql.Identifier(store.schema,'event_footers')
    with store.connect() as conn:
        found=conn.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()),(event_id,)).fetchone()
        if not found:return None
        owner=found[0].get('parent_event_id',event_id)
        conn.execute(sql.SQL('SELECT id FROM {} WHERE id=%s FOR UPDATE').format(store.table()),(owner,))
        row=conn.execute(sql.SQL('SELECT body,revision FROM {} WHERE event_id=%s').format(table),(owner,)).fetchone()
        if row:
            body,revision=row
            body=dict(body,footer=normalize(body.get('footer',{})))
        else:
            rows=conn.execute(sql.SQL("SELECT p.event_id,p.body->'appearance'->'footer',COALESCE(f.name,'Original event') FROM {} p JOIN {} e ON e.id=p.event_id LEFT JOIN {} f ON f.id=p.event_id WHERE e.id=%s OR e.body->>'parent_event_id'=%s").format(store.page_table(),store.table(),sql.Identifier(store.schema,'registration_flows')),(owner,owner)).fetchall()
            legacy=[dict(flow_id=str(r[0]),name=r[2],footer=normalize(r[1] or {})) for r in rows]
            empty=normalize({});unique={json.dumps(r['footer'],sort_keys=True):r['footer'] for r in legacy if r['footer']!=empty}
            body=dict(footer=next(iter(unique.values())) if len(unique)==1 else empty,legacy=legacy,conflict=len(unique)>1)
            revision=0
            conn.execute(sql.SQL('INSERT INTO {}(event_id,body,revision) VALUES(%s,%s,0)').format(table),(owner,Jsonb(body)))
        if data is not None:
            if not isinstance(data,dict) or type(data.get('revision')) is not int or data['revision']!=revision:
                raise ValueError('The shared footer changed. Reload before saving again.')
            if body['conflict'] and data.get('resolve_conflict') is not True:
                raise ValueError('Choose and review the footer to share before resolving the different legacy footers.')
            footer=normalize(data.get('footer'))
            if footer['logo_asset_id'] and not conn.execute(sql.SQL("SELECT 1 FROM {} WHERE id=%s AND event_id=%s AND kind='logo'").format(sql.Identifier(store.schema,'registration_assets')),(footer['logo_asset_id'],owner)).fetchone():
                raise ValueError('Choose a footer logo uploaded for this event.')
            if footer['background_asset_id'] and not conn.execute(sql.SQL("SELECT 1 FROM {} WHERE id=%s AND event_id=%s AND kind='background'").format(sql.Identifier(store.schema,'registration_assets')),(footer['background_asset_id'],owner)).fetchone():
                raise ValueError('Choose a footer background uploaded for this event.')
            body=dict(body,footer=footer,conflict=False)
            revision+=1
            conn.execute(sql.SQL('UPDATE {} SET body=%s,revision=%s WHERE event_id=%s').format(table),(Jsonb(body),revision,owner))
        return dict(event_id=owner,revision=revision,**{**body,'footer':{**body['footer'],**({'asset_event_id':owner} if body['footer'].get('logo_asset_id') or body['footer'].get('background_asset_id') else {})}})
