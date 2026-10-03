"""Flow-specific agenda, validated append-only import and optimistic draft saves."""
import csv
import io
import json
import hashlib
import uuid
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from registration import text, local_instant, CURRENCIES
from psycopg import sql
from psycopg.types.json import Jsonb

FIELDS = ('title', 'date', 'start_time', 'end_time', 'location', 'track', 'speaker', 'description', 'price', 'credits', 'status', 'cancellation_note')
REQUIRED = FIELDS[:4]
MAX_SESSIONS = 500


def validate(data, event):
    if not isinstance(data, dict): raise ValueError('Send a sessions page.')
    currency = data.get('currency', 'USD')
    if not isinstance(currency, str) or currency not in CURRENCIES: raise ValueError('Choose a supported currency.')
    rows = data.get('sessions')
    if not isinstance(rows, list) or len(rows) > MAX_SESSIONS: raise ValueError('Use up to 500 sessions.')
    speakers=data.get('speakers',[])
    if not isinstance(speakers,list) or len(speakers)>500:raise ValueError('Use up to 500 speaker profiles.')
    profiles=[];speaker_ids=set()
    for speaker in speakers:
        if not isinstance(speaker,dict):raise ValueError('Invalid speaker profile.')
        try:sid=str(uuid.UUID(speaker.get('id','')))
        except (ValueError,TypeError,AttributeError):raise ValueError('Each speaker needs a valid ID.')
        if sid in speaker_ids:raise ValueError('Speaker IDs must be unique.')
        speaker_ids.add(sid);profile=dict(id=sid)
        for key,limit in [('first_name',100),('last_name',100),('bio',3000),('role',200),('organization',200)]:
            profile[key]=text(speaker.get(key,''),'Speaker '+key,limit,key in ('first_name','last_name'))
        photo=speaker.get('photo_asset_id')
        if photo is not None:
            try:photo=str(uuid.UUID(photo))
            except (ValueError,TypeError,AttributeError):raise ValueError('Invalid speaker photo.')
        profile['photo_asset_id']=photo;profiles.append(profile)
    result = dict(currency=currency, sessions=[],speakers=profiles)
    seen = set()
    for row in rows:
        if not isinstance(row, dict): raise ValueError('Each session must be an object.')
        try: sid = str(uuid.UUID(row.get('id', '')))
        except (ValueError, TypeError, AttributeError): raise ValueError('Each session needs a valid ID.')
        if sid in seen: raise ValueError('Session IDs must be unique.')
        seen.add(sid)
        linked=row.get('speaker_ids',[])
        if not isinstance(linked,list) or any(not isinstance(v,str) or v not in speaker_ids for v in linked) or len(set(linked))!=len(linked):raise ValueError('Choose existing speakers for this flow.')
        item = dict(id=sid,speaker_ids=linked)
        for key, limit in [('title',200),('location',200),('track',100),('speaker',300),('description',5000)]:
            item[key] = text(row.get(key, ''), key.replace('_',' ').capitalize(), limit, key=='title')
        for key in ('start','end'):
            value = row.get(key)
            instant = local_instant(value, event['timezone'], 'Session '+key)
            # Reject ambiguous fall-back times rather than silently choosing an occurrence.
            local = instant.astimezone(ZoneInfo(event['timezone']))
            if local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset():
                raise ValueError('Session '+key+' is ambiguous during the daylight-saving change. Choose an unambiguous time.')
            item[key] = value
            item[key+'_utc'] = instant.isoformat()
        if item['end_utc'] <= item['start_utc']: raise ValueError('Session end must be after its start.')
        if item['start'][:10] != item['end'][:10]: raise ValueError('Split overnight sessions into one session per date.')
        price = row.get('price_minor',0)
        if type(price) is not int or not 0 <= price <= 99999999: raise ValueError('Enter a valid non-negative session price.')
        item['price_minor'] = price
        credits=row.get('credits')
        if credits is not None:
            if type(credits) not in (int,float) or not 0 <= credits <= 10000 or Decimal(str(credits))*100 != (Decimal(str(credits))*100).to_integral_value():
                raise ValueError('CEU / CEM credits must be between 0 and 10,000 with up to two decimal places.')
        item['credits']=credits
        status=row.get('status','active')
        if status not in ('active','canceled'):raise ValueError('Choose Active or Canceled for session status.')
        item['status']=status
        item['cancellation_note']=text(row.get('cancellation_note',''),'Cancellation note',1000)
        result['sessions'].append(item)
    result['sessions'].sort(key=lambda x:(x['start'],x['title'].casefold(),x['id']))
    return result


def parse_file(content):
    if not isinstance(content,str) or not content.strip() or len(content.encode('utf-8')) > 2_000_000:
        raise ValueError('Choose a nonempty UTF-8 CSV or TSV file under 2 MB.')
    content=content.lstrip('\ufeff')
    try:
        dialect=csv.Sniffer().sniff(content[:8192],delimiters=',\t')
    except csv.Error:
        dialect=csv.excel_tab if '\t' in content.splitlines()[0] else csv.excel
    try:
        reader=csv.reader(io.StringIO(content),dialect=dialect,strict=True)
        headers=[h.strip() for h in next(reader)]
        if not 1 <= len(headers) <= 40 or not all(headers) or len(set(headers))!=len(headers):
            raise ValueError('Use 1–40 distinct, nonempty column headings.')
        rows=[]
        for number,values in enumerate(reader,2):
            if not any(v.strip() for v in values): continue
            if len(values)!=len(headers): raise ValueError(f'Row {number}: column count does not match the header.')
            rows.append((number,dict(zip(headers,values))))
            if len(rows)>MAX_SESSIONS: raise ValueError('Import up to 500 sessions at a time.')
        if not rows: raise ValueError('The file has headings but no session rows.')
        return headers,rows
    except (csv.Error,StopIteration) as exc: raise ValueError('Could not read this CSV/TSV. Check quoting and column headings.') from exc


def import_preview(data,event,currency):
    headers,rows=parse_file(data.get('content'))
    mapping=data.get('mapping')
    if mapping is None: return dict(headers=headers, sample=[row for _,row in rows[:3]], count=len(rows))
    if not isinstance(mapping,dict) or any(k not in FIELDS for k in mapping): raise ValueError('Use valid column mappings.')
    if any(not isinstance(v,str) or (v and v not in headers) for v in mapping.values()): raise ValueError('Choose existing columns.')
    if any(not mapping.get(k) for k in REQUIRED): raise ValueError('Map title, date, start time and end time.')
    used=[v for v in mapping.values() if v]
    if len(used)!=len(set(used)): raise ValueError('Map each source column only once.')
    normalized=[];errors=[]
    for number,row in rows:
        val=lambda k:row.get(mapping.get(k),'').strip()
        try:
            price=Decimal(val('price') or '0')
            scale=10**CURRENCIES[currency]
            if not price.is_finite() or price<0 or price*scale!=(price*scale).to_integral_value():
                raise ValueError('Price must be a non-negative amount with the correct currency precision.')
            item={k:val(k) for k in ('title','location','track','speaker','description')}
            # Stable IDs tie confirmation to the exact content + mapping; re-import duplicates are rejected.
            id_mapping={k:v for k,v in mapping.items() if k in FIELDS[:9] or v}
            item.update(id=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps([event['id'],number,row,id_mapping],sort_keys=True))),start=val('date')+'T'+val('start_time'),end=val('date')+'T'+val('end_time'),price_minor=int(price*scale),credits=float(val('credits')) if val('credits') else None,status=(val('status') or 'active').lower(),cancellation_note=val('cancellation_note'))
            normalized.append(validate(dict(currency=currency,sessions=[item]),event)['sessions'][0])
        except (ValueError,InvalidOperation,OverflowError) as exc: errors.append(dict(row=number,message=str(exc)))
    digest=hashlib.sha256(json.dumps([currency,normalized,errors],sort_keys=True).encode()).hexdigest()
    return dict(headers=headers,sessions=normalized,errors=errors,count=len(rows),digest=digest)


def operation(store,event_id,action='get',data=None):
    data=data or {}
    if not isinstance(data,dict): raise ValueError('Send a sessions object.')
    table=sql.Identifier(store.schema,'event_sessions')
    with store.connect() as conn:
        row=conn.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()),(event_id,)).fetchone()
        if not row: return None
        owner=row[0].get('parent_event_id',event_id)
        parent=conn.execute(sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(store.table()),(owner,)).fetchone()
        if not parent:return None
        event=parent[0]
        flow=conn.execute(sql.SQL('SELECT name FROM {} WHERE id=%s AND NOT archived').format(sql.Identifier(store.schema,'registration_flows')),(event_id,)).fetchone()
        if not flow: return None
        record=conn.execute(sql.SQL('SELECT body,revision FROM {} WHERE event_id=%s').format(table),(event_id,)).fetchone()
        page=record[0] if record else dict(currency='USD',sessions=[])
        revision=record[1] if record else 0
        # Compute instants from the current event timezone, never trust imported UTC fields.
        page=validate(page,event)
        event={**event,'id':event_id}
        metadata=dict(event_id=event_id,parent_event_id=owner,flow_name=flow[0],event_name=event['name'],timezone=event['timezone'],revision=revision)
        if action=='get': return page|metadata
        if action=='import-preview': return import_preview(data,event,page['currency'])|dict(revision=revision)
        if type(data.get('revision')) is not int or data['revision']!=revision:
            raise ValueError('Sessions changed in another tab. Reload sessions before saving; your edits are still here.')
        if action=='save': page=validate(data,event)
        elif action=='import':
            preview=import_preview(data,event,page['currency'])
            if preview.get('errors') or not preview.get('sessions') or data.get('digest')!=preview.get('digest'):
                raise ValueError('Preview this exact file and mapping and fix all errors before importing.')
            page=validate(dict(currency=page['currency'],sessions=page['sessions']+preview['sessions'],speakers=page['speakers']),event)
        else: raise ValueError('Unknown sessions action.')
        for profile in page['speakers']:
            if profile['photo_asset_id'] and not conn.execute(sql.SQL('SELECT 1 FROM {} WHERE id=%s AND event_id=%s').format(sql.Identifier(store.schema,'registration_assets')),(profile['photo_asset_id'],event_id)).fetchone():
                raise ValueError('Speaker photo must belong to this registration flow.')
        conn.execute(sql.SQL('INSERT INTO {}(event_id,body,revision) VALUES(%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET body=excluded.body,revision=excluded.revision').format(table),(event_id,Jsonb(page),revision+1))
        return page|metadata|dict(revision=revision+1)
