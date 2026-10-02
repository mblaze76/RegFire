"""PostgreSQL storage with private local connection settings."""
import json
from pathlib import Path
import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / '.local' / 'postgres.json'


def settings():
    if not CONFIG.exists():
        raise RuntimeError('Run .venv/bin/python setup_postgres.py in Terminal first.')
    if CONFIG.stat().st_mode & 0o077:
        raise RuntimeError('Connection settings must be private: chmod 600 .local/postgres.json')
    return json.loads(CONFIG.read_text())


class Store:
    def __init__(self, config=None, schema='regfire'):
        self.config = config if config is not None else settings()
        self.schema = schema

    def connect(self):
        return psycopg.connect(**self.config, connect_timeout=5)

    def table(self):
        return psycopg.sql.Identifier(self.schema, 'events')

    def page_table(self):
        return psycopg.sql.Identifier(self.schema, 'registration_pages')

    def initialize(self):
        with self.connect() as conn:
            conn.execute(psycopg.sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(psycopg.sql.Identifier(self.schema)))
            conn.execute(psycopg.sql.SQL('CREATE TABLE IF NOT EXISTS {} (id UUID PRIMARY KEY, body JSONB NOT NULL, updated TIMESTAMPTZ NOT NULL)').format(self.table()))
            for path in sorted((ROOT / 'migrations').glob('*.sql')):
                conn.execute(psycopg.sql.SQL(path.read_text()).format(schema=psycopg.sql.Identifier(self.schema)))

    def list(self):
        with self.connect() as conn:
            return [r[0] for r in conn.execute(psycopg.sql.SQL("SELECT body FROM {} WHERE NOT (body ? 'parent_event_id') ORDER BY updated DESC, id").format(self.table()))]

    def save(self, event_id, data, now, editing):
        with self.connect() as conn:
            old = conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(self.table()), (event_id,)).fetchone()
            if editing and not old:
                return None
            if old and old[0].get('parent_event_id'): data['parent_event_id']=old[0]['parent_event_id']
            data.update(id=event_id, status='draft', created=old[0]['created'] if old else now, updated=now)
            if editing:
                existing_page = conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(self.page_table()), (event_id,)).fetchone()
                if existing_page:
                    from registration import validate_page
                    validate_page(existing_page[0], data['timezone'])
                conn.execute(psycopg.sql.SQL('UPDATE {} SET body=%s, updated=%s WHERE id=%s').format(self.table()), (Jsonb(data), now, event_id))
            else:
                conn.execute(psycopg.sql.SQL('INSERT INTO {} (id,body,updated) VALUES(%s,%s,%s)').format(self.table()), (event_id, Jsonb(data), now))
            if not data.get('parent_event_id'):
                flows=psycopg.sql.Identifier(self.schema,'registration_flows')
                conn.execute(psycopg.sql.SQL("INSERT INTO {}(id,event_id,name,kind,position) VALUES(%s,%s,'Attendee','attendee',0) ON CONFLICT(id) DO NOTHING").format(flows),(event_id,event_id))
                children=conn.execute(psycopg.sql.SQL("SELECT id,body FROM {} WHERE body->>'parent_event_id'=%s").format(self.table()),(event_id,)).fetchall()
                for child_id,body in children:
                    child_page=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(self.page_table()),(child_id,)).fetchone()
                    if child_page:
                        from registration import validate_page
                        validate_page(child_page[0],data['timezone'])
                    body.update({key:value for key,value in data.items() if key not in ('id','created','updated')})
                    conn.execute(psycopg.sql.SQL('UPDATE {} SET body=%s WHERE id=%s').format(self.table()),(Jsonb(body),child_id))
            return data

    def flows(self,event_id,change=None,now=None):
        import uuid
        table=psycopg.sql.Identifier(self.schema,'registration_flows')
        with self.connect() as conn:
            row=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(self.table()),(event_id,)).fetchone()
            if not row or row[0].get('parent_event_id'):return None
            event=row[0]
            if change is not None:
                if not isinstance(change,dict):raise ValueError('A flow object is required.')
                action=change.get('action','create')
                if action in ('create','rename'):
                    name=change.get('name','')
                    if not isinstance(name,str) or not name.strip() or len(name)>100:raise ValueError('Enter a flow name of 1 to 100 characters.')
                    if action=='create':
                        kind=change.get('kind','custom')
                        if kind not in ('attendee','exhibitor','media','custom'):raise ValueError('Choose a supported flow type.')
                        child_id=str(uuid.uuid4());body={**event,'id':child_id,'parent_event_id':event_id,'created':now,'updated':now}
                        conn.execute(psycopg.sql.SQL('INSERT INTO {}(id,body,updated) VALUES(%s,%s,%s)').format(self.table()),(child_id,Jsonb(body),now))
                        position=conn.execute(psycopg.sql.SQL('SELECT COALESCE(MAX(position),-1)+1 FROM {} WHERE event_id=%s').format(table),(event_id,)).fetchone()[0]
                        conn.execute(psycopg.sql.SQL('INSERT INTO {}(id,event_id,name,kind,position) VALUES(%s,%s,%s,%s,%s)').format(table),(child_id,event_id,name.strip(),kind,position))
                    else:
                        if not conn.execute(psycopg.sql.SQL('UPDATE {} SET name=%s WHERE id=%s AND event_id=%s AND NOT archived RETURNING id').format(table),(name.strip(),change.get('id'),event_id)).fetchone():raise ValueError('Flow not found.')
                elif action=='remove':
                    flow=conn.execute(psycopg.sql.SQL('SELECT name FROM {} WHERE id=%s AND event_id=%s AND NOT archived FOR UPDATE').format(table),(change.get('id'),event_id)).fetchone()
                    if not flow:raise ValueError('Flow not found.')
                    if change.get('confirm_name')!=flow[0]:raise ValueError('Confirm the current flow name before removing it.')
                    conn.execute(psycopg.sql.SQL('UPDATE {} SET archived=TRUE WHERE id=%s AND event_id=%s').format(table),(change.get('id'),event_id))
                elif action=='reorder':
                    ids=change.get('ids');existing=[str(r[0]) for r in conn.execute(psycopg.sql.SQL('SELECT id FROM {} WHERE event_id=%s AND NOT archived').format(table),(event_id,))]
                    if not isinstance(ids,list) or len(ids)!=len(existing) or set(ids)!=set(existing):raise ValueError('Include every flow exactly once.')
                    for position,flow_id in enumerate(ids):conn.execute(psycopg.sql.SQL('UPDATE {} SET position=%s WHERE id=%s AND event_id=%s').format(table),(position,flow_id,event_id))
                else:raise ValueError('Unknown flow action.')
            rows=conn.execute(psycopg.sql.SQL('SELECT id,name,kind,position FROM {} WHERE event_id=%s AND NOT archived ORDER BY position,id').format(table),(event_id,)).fetchall()
            return [dict(id=str(r[0]),name=r[1],kind=r[2],position=r[3],event_id=event_id) for r in rows]

    def welcome_page(self, event_id, data=None, now=None):
        from welcome import validate
        table = psycopg.sql.Identifier(self.schema, 'welcome_pages')
        with self.connect() as conn:
            if not conn.execute(psycopg.sql.SQL('SELECT id FROM {} WHERE id=%s FOR UPDATE').format(self.table()), (event_id,)).fetchone(): return None
            row=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(table), (event_id,)).fetchone()
            existing=row[0] if row else dict(event_id=event_id,about='',logo_asset_id=None,sponsor_asset_ids=[],updated=None,status='draft')
            if existing.get('buttons') is None:
                rows=conn.execute(psycopg.sql.SQL('SELECT id,name FROM {} WHERE event_id=%s AND NOT archived ORDER BY position,id').format(psycopg.sql.Identifier(self.schema,'registration_flows')),(event_id,)).fetchall()
                existing['buttons']=[dict(id=str(r[0]),label=r[1],flow_id=str(r[0])) for r in rows]
                conn.execute(psycopg.sql.SQL('INSERT INTO {}(event_id,body,updated) VALUES(%s,%s,CURRENT_TIMESTAMP) ON CONFLICT(event_id) DO UPDATE SET body=excluded.body').format(table),(event_id,Jsonb(existing)))
            if data is not None:
                data = validate(data)
                if data['buttons'] is None:data['buttons']=existing['buttons']
                for button in data['buttons']:
                    if button['flow_id'] and not conn.execute(psycopg.sql.SQL('SELECT 1 FROM {} WHERE id=%s AND event_id=%s').format(psycopg.sql.Identifier(self.schema,'registration_flows')),(button['flow_id'],event_id)).fetchone():
                        raise ValueError('Choose a registration flow belonging to this event.')
                ids = ([data['logo_asset_id']] if data['logo_asset_id'] else []) + data['sponsor_asset_ids']
                for asset_id in ids:
                    if not conn.execute(psycopg.sql.SQL("SELECT 1 FROM {} WHERE id=%s AND event_id=%s AND kind='logo'").format(psycopg.sql.Identifier(self.schema, 'registration_assets')), (asset_id,event_id)).fetchone():
                        raise ValueError('That logo is missing or belongs to another event.')
                if data['background_asset_id'] and not conn.execute(psycopg.sql.SQL("SELECT 1 FROM {} WHERE id=%s AND event_id=%s AND kind='background'").format(psycopg.sql.Identifier(self.schema,'registration_assets')),(data['background_asset_id'],event_id)).fetchone():
                    raise ValueError('That background is missing or belongs to another event.')
                data.update(event_id=event_id, updated=now, status='draft')
                conn.execute(psycopg.sql.SQL('INSERT INTO {} (event_id,body,updated) VALUES(%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET body=excluded.body, updated=excluded.updated').format(table), (event_id,Jsonb(data),now))
                return data
            return existing

    def registration_page(self, event_id):
        from registration import starter
        with self.connect() as conn:
            event = conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE id=%s').format(self.table()), (event_id,)).fetchone()
            if not event: return None
            page = conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(self.page_table()), (event_id,)).fetchone()
            return page[0] if page else starter(event[0])

    def save_registration_page(self, event_id, data, now):
        with self.connect() as conn:
            event = conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(self.table()), (event_id,)).fetchone()
            if not event: return None
            from registration import validate_page
            data = validate_page(data, event[0]['timezone'])
            for key,kind in [('logo_asset_id','logo'),('background_asset_id','background')]:
                asset_id=data['appearance'][key]
                if asset_id and not conn.execute(psycopg.sql.SQL('SELECT 1 FROM {} WHERE id=%s AND event_id=%s AND kind=%s').format(psycopg.sql.Identifier(self.schema,'registration_assets')),(asset_id,event_id,kind)).fetchone():
                    raise ValueError('That image is missing or belongs to a different event. Upload or select an image for this event.')
            existing_demographics=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(psycopg.sql.Identifier(self.schema,'demographics_pages')),(event_id,)).fetchone()
            if existing_demographics:
                from demographics import validate as validate_demographics
                validate_demographics(existing_demographics[0],data['regtypes'])
            membership=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(psycopg.sql.Identifier(self.schema,'membership_settings')),(event_id,)).fetchone()
            if membership:
                from membership import validate as validate_membership
                validate_membership(membership[0],data['regtypes'])
            data.update(event_id=event_id, status='draft', updated=now)
            conn.execute(psycopg.sql.SQL('INSERT INTO {} (event_id,body,updated) VALUES(%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET body=excluded.body, updated=excluded.updated').format(self.page_table()), (event_id, Jsonb(data), now))
            return data

    def preview_registration_pricing(self, event_id, data, at=''):
        from registration import pricing_preview
        with self.connect() as conn:
            event=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE id=%s').format(self.table()), (event_id,)).fetchone()
            if not event: return None
            return pricing_preview(data,event[0]['timezone'],at)

    def save_asset(self, event_id, kind, content, upload_root=None):
        import uuid
        from datetime import datetime,timezone
        from assets import normalize_image
        normalized=normalize_image(content)
        asset_id=str(uuid.uuid4());filename=asset_id+'.png'
        root=upload_root or ROOT/'uploads';root.mkdir(mode=0o700,parents=True,exist_ok=True)
        path=root/filename
        try:
            with self.connect() as conn:
                if not conn.execute(psycopg.sql.SQL('SELECT id FROM {} WHERE id=%s FOR KEY SHARE').format(self.table()),(event_id,)).fetchone(): return None
                with path.open('xb') as file:file.write(normalized)
                path.chmod(0o600)
                conn.execute(psycopg.sql.SQL('INSERT INTO {} (id,event_id,kind,filename,mime,byte_size,created) VALUES(%s,%s,%s,%s,%s,%s,%s)').format(psycopg.sql.Identifier(self.schema,'registration_assets')),(asset_id,event_id,kind,filename,'image/png',len(normalized),datetime.now(timezone.utc)))
            return dict(id=asset_id,kind=kind,url='/api/events/'+event_id+'/assets/'+asset_id)
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def asset(self,event_id,asset_id):
        with self.connect() as conn:
            row=conn.execute(psycopg.sql.SQL('SELECT filename,mime FROM {} WHERE event_id=%s AND id=%s').format(psycopg.sql.Identifier(self.schema,'registration_assets')),(event_id,asset_id)).fetchone()
            return row

    def demographics_page(self,event_id):
        from demographics import starter
        with self.connect() as conn:
            if not conn.execute(psycopg.sql.SQL('SELECT id FROM {} WHERE id=%s').format(self.table()),(event_id,)).fetchone():return None
            row=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(psycopg.sql.Identifier(self.schema,'demographics_pages')),(event_id,)).fetchone()
            return row[0] if row else starter(event_id)

    def demographics_operation(self,event_id,data,answers=None,regtype_id=None,check=False,preview_registration=None):
        from demographics import validate,evaluate
        from registration import starter
        from datetime import datetime,timezone
        with self.connect() as conn:
            event=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(self.table()),(event_id,)).fetchone()
            if not event:return None
            registration=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(self.page_table()),(event_id,)).fetchone()
            regtypes=(registration[0] if registration else starter(event[0]))['regtypes']
            if answers is not None:
                if preview_registration is not None:
                    from registration import validate_page
                    regtypes=validate_page(preview_registration,event[0]['timezone'])['regtypes']
                return evaluate(data,regtypes,regtype_id,answers,check)
            normalized=validate(data,regtypes);now=datetime.now(timezone.utc).isoformat()
            normalized.update(event_id=event_id,status='draft',updated=now)
            conn.execute(psycopg.sql.SQL('INSERT INTO {} (event_id,body,updated) VALUES(%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET body=excluded.body,updated=excluded.updated').format(psycopg.sql.Identifier(self.schema,'demographics_pages')),(event_id,Jsonb(normalized),now))
            return normalized

    def membership(self,event_id,action='get',data=None):
        from membership import starter,validate,parse_csv,summary,digest,lookup_keys,matches,api_lookup,outcome,Unavailable
        from registration import starter as registration_starter
        from datetime import datetime,timezone
        data=data or {};now=datetime.now(timezone.utc).isoformat()
        settings_table=psycopg.sql.Identifier(self.schema,'membership_settings')
        imports_table=psycopg.sql.Identifier(self.schema,'membership_imports')
        with self.connect() as conn:
            ev=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(self.table()),(event_id,)).fetchone()
            if not ev:return None
            reg=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(self.page_table()),(event_id,)).fetchone()
            regtypes=(reg[0] if reg else registration_starter(ev[0]))['regtypes']
            saved=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(settings_table),(event_id,)).fetchone()
            config=saved[0] if saved else starter()
            imported=conn.execute(psycopg.sql.SQL('SELECT records,digest,updated FROM {} WHERE event_id=%s').format(imports_table),(event_id,)).fetchone()
            info=dict(count=len(imported[0]) if imported else 0,revision=imported[1] if imported else '',updated=imported[2].isoformat() if imported else None)
            if action=='get':return dict(config=config,import_info=info,timezone=ev[0]['timezone'])
            if action=='save':
                config=validate(data,regtypes)
                conn.execute(psycopg.sql.SQL('INSERT INTO {} (event_id,body,updated) VALUES(%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET body=excluded.body,updated=excluded.updated').format(settings_table),(event_id,Jsonb(config),now))
                return dict(config=config,import_info=info,timezone=ev[0]['timezone'])
            if action in ('import-preview','import'):
                rows=parse_csv(data.get('csv'),data.get('mapping'));result=summary(rows)
                if action=='import':
                    if data.get('digest')!=result['digest']:raise ValueError('Preview this exact file and mapping before replacing members.')
                    if data.get('revision')!=info['revision']:raise ValueError('The member list changed. Preview and confirm replacement again.')
                    conn.execute(psycopg.sql.SQL('INSERT INTO {} (event_id,records,digest,updated) VALUES(%s,%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET records=excluded.records,digest=excluded.digest,updated=excluded.updated').format(imports_table),(event_id,Jsonb(rows),result['digest'],now))
                    return dict(count=len(rows),revision=result['digest'],updated=now)
                result['revision']=info['revision'];return result
            if action not in ('lookup','test'):raise ValueError('Unknown membership action.')
            config=validate(data.get('config',config),regtypes)
            regtype=data.get('regtype_id')
            if action=='lookup' and regtype not in {r['id'] for r in regtypes}:raise ValueError('Choose an existing RegType.')
            if action=='lookup' and (not config['enabled'] or regtype not in config['regtype_ids']):return outcome(config,None,ev[0]['timezone'],applies=False)
            keys=lookup_keys(data)
            unavailable=False;record=None
            if config['source']=='api' or action=='test':
                if not config['api']['endpoint']:raise ValueError('Add an API endpoint first.')
                try:record=api_lookup(config,keys)
                except Unavailable:unavailable=True
            else:
                if not imported:unavailable=True
                else:record=next((r for r in imported[0] if matches(r,keys)),None)
            if action=='test':return dict(connected=not unavailable,message='Adapter responded with a valid matching member.' if record else 'Adapter responded with no match.' if not unavailable else 'Connection could not be verified. Check endpoint, adapter response and server credential settings.',fixture=config['api']['endpoint']=='fixture://demo')
            result=outcome(config,record,ev[0]['timezone'],unavailable=unavailable)
            result['fixture']=config['source']=='api' and config['api']['endpoint']=='fixture://demo'
            return result

    def delete_event(self,event_id,expected_name,upload_root=None):
        import re
        with self.connect() as conn:
            row=conn.execute(psycopg.sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(self.table()),(event_id,)).fetchone()
            if not row:return None
            if row[0]['name']!=expected_name:raise ValueError('This event was renamed. Reload and confirm deletion using its current name.')
            flow_ids=[r[0] for r in conn.execute(psycopg.sql.SQL('SELECT id FROM {} WHERE event_id=%s').format(psycopg.sql.Identifier(self.schema,'registration_flows')),(event_id,))]
            ids=list(set(flow_ids+[__import__('uuid').UUID(event_id)]))
            assets=conn.execute(psycopg.sql.SQL('SELECT filename FROM {} WHERE event_id=ANY(%s)').format(psycopg.sql.Identifier(self.schema,'registration_assets')),(ids,)).fetchall()
            conn.execute(psycopg.sql.SQL('DELETE FROM {} WHERE id=ANY(%s)').format(self.table()),(ids,))
        remaining=0;root=upload_root or ROOT/'uploads'
        for (filename,) in assets:
            if re.fullmatch(r'[a-f0-9-]{36}\.png',filename):
                try:(root/filename).unlink(missing_ok=True)
                except OSError:remaining+=1
        return dict(deleted=event_id,retained_image_files=remaining)
