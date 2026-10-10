"""Flow-scoped optional items and nonbinding selection totals; no reservations or checkout."""
import json,re,uuid
from urllib.parse import urlsplit
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from registration import text,CURRENCIES

def inventory(value):
    if value is not None and (type(value) is not int or not 0<=value<=1000000):raise ValueError('Inventory must be a whole number from 0 to 1,000,000, or blank for unlimited.')
    return value

def validate(data):
    if not isinstance(data,dict):raise ValueError('Send extra options settings.')
    currency=data.get('currency','USD')
    if not isinstance(currency,str) or currency not in CURRENCIES:raise ValueError('Choose a supported currency.')
    items=data.get('items',[])
    if not isinstance(items,list) or len(items)>100:raise ValueError('Use up to 100 extra options.')
    result=[];seen=set()
    def ident(value):
        try:value=str(uuid.UUID(value))
        except (ValueError,TypeError,AttributeError):raise ValueError('Each item and variant needs a valid ID.')
        if value in seen:raise ValueError('Item and variant IDs must be unique.')
        seen.add(value);return value
    for row in items:
        if not isinstance(row,dict):raise ValueError('Invalid extra option.')
        item=dict(id=ident(row.get('id')),name=text(row.get('name'),'Item name',200,True),description=text(row.get('description',''),'Description',3000))
        kind=row.get('kind','physical')
        if kind not in ('physical','service'):raise ValueError('Choose a physical item or service / experience.')
        price=row.get('price_minor',0)
        if type(price) is not int or not 0<=price<=99999999:raise ValueError('Enter a valid non-negative item price.')
        for flag in ('allow_multiple','taxable'):
            if type(row.get(flag,False)) is not bool:raise ValueError('Use on or off for item settings.')
        if kind!='physical' and row.get('taxable',False):raise ValueError('The tax setting is available for physical items.')
        variants=row.get('variants',[])
        if not isinstance(variants,list) or len(variants)>50:raise ValueError('Use up to 50 variants per item.')
        options=[];labels=set()
        for v in variants:
            if not isinstance(v,dict):raise ValueError('Invalid variant.')
            label=text(v.get('label'),'Variant / size',100,True)
            if label.casefold() in labels:raise ValueError('Variant names must be unique within an item.')
            labels.add(label.casefold());options.append(dict(id=ident(v.get('id')),label=label,inventory=inventory(v.get('inventory'))))
        item.update(kind=kind,price_minor=price,inventory=inventory(row.get('inventory')),allow_multiple=row.get('allow_multiple',False),taxable=row.get('taxable',False),variants=options)
        if options and item['inventory'] is not None:raise ValueError('Use per-variant inventory when variants are present.')
        result.append(item)
    return dict(currency=currency,items=result)

def quote(page,selections):
    page=validate(page)
    if not isinstance(selections,list) or len(selections)>500:raise ValueError('Send a list of selected items.')
    items={i['id']:i for i in page['items']};seen=set();totals={};lines=[]
    for row in selections:
        if not isinstance(row,dict) or not isinstance(row.get('item_id'),str) or row['item_id'] not in items:raise ValueError('An item is no longer available.')
        item=items[row['item_id']];variant=row.get('variant_id');key=(item['id'],variant)
        if variant is not None and not isinstance(variant,str):raise ValueError('Choose a valid variant.')
        if key in seen:raise ValueError('Combine duplicate selections.');
        seen.add(key);qty=row.get('quantity')
        if type(qty) is not int or not 1<=qty<=99:raise ValueError('Choose a quantity from 1 to 99.')
        totals[item['id']]=totals.get(item['id'],0)+qty
        if not item['allow_multiple'] and totals[item['id']]>1:raise ValueError(item['name']+' allows one selection.')
        option=next((v for v in item['variants'] if v['id']==variant),None)
        if item['variants'] and not option or not item['variants'] and variant is not None:raise ValueError('Choose an available variant.')
        stock=option['inventory'] if option else item['inventory']
        if stock is not None and qty>stock:raise ValueError(item['name']+(' is sold out.' if stock==0 else ' has only '+str(stock)+' available.'))
        lines.append(dict(item_id=item['id'],variant_id=variant,name=item['name'],variant=option['label'] if option else None,quantity=qty,unit_price_minor=item['price_minor'],line_total_minor=qty*item['price_minor'],taxable=item['taxable']))
    return dict(currency=page['currency'],lines=lines,item_subtotal_minor=sum(l['line_total_minor'] for l in lines),tax_pending=any(l['taxable'] for l in lines),reserved=False)

def operation(store,event_id,action='get',data=None):
    data={} if data is None else data
    if not isinstance(data,dict):raise ValueError('Send extra options settings.')
    table=sql.Identifier(store.schema,'extra_options')
    with store.connect() as c:
        row=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()),(event_id,)).fetchone()
        if not row:return None
        parent=row[0].get('parent_event_id',event_id)
        event=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(store.table()),(parent,)).fetchone()
        flow=c.execute(sql.SQL('SELECT name FROM {} WHERE id=%s AND NOT archived').format(sql.Identifier(store.schema,'registration_flows')),(event_id,)).fetchone()
        if not event or not flow:return None
        record=c.execute(sql.SQL('SELECT body,revision FROM {} WHERE event_id=%s').format(table),(event_id,)).fetchone()
        page=validate(record[0] if record else {});revision=record[1] if record else 0
        meta=dict(event_id=event_id,parent_event_id=parent,event_name=event[0]['name'],flow_name=flow[0],revision=revision)
        if action=='get':return page|meta
        if action=='quote':return quote(page,data.get('selections'))|dict(revision=revision)
        if action!='save':raise ValueError('Unknown extra options action.')
        if type(data.get('revision')) is not int or data['revision']!=revision:raise ValueError('Extra options changed in another tab. Reload before saving; your edits are still here.')
        page=validate(data)
        c.execute(sql.SQL('INSERT INTO {}(event_id,body,revision) VALUES(%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET body=excluded.body,revision=excluded.revision').format(table),(event_id,Jsonb(page),revision+1))
        return page|meta|dict(revision=revision+1)

def handle(h):
    path=urlsplit(h.path).path
    files={'/extras':'extras.html','/extras-builder.js':'extras-builder.js','/extras-common.js':'extras-common.js','/extras-site.js':'extras-site.js','/extras.css':'extras.css'}
    if h.command=='GET' and path in files:
        content=(Path(__file__).parent/'static'/files[path]).read_bytes();h.send_response(200);h.send_header('Content-Type','text/html' if path=='/extras' else 'text/css' if path.endswith('.css') else 'text/javascript');h.send_header('Content-Length',str(len(content)));h.send_header('X-Content-Type-Options','nosniff');h.send_header('Referrer-Policy','same-origin');h.send_header('X-Frame-Options','SAMEORIGIN');h.send_header('Cache-Control','no-store');h.end_headers();h.wfile.write(content);return True
    m=re.fullmatch(r'/api/events/([a-f0-9-]{36})/extra-options(/quote)?',path)
    if not m:return False
    try:
        action='quote' if m[2] and h.command=='POST' else 'get' if not m[2] and h.command=='GET' else 'save' if not m[2] and h.command=='PUT' else None
        if not action:h.respond(405,{'error':'Method not allowed.'});return True
        data=None
        if action!='get':
            size=int(h.headers.get('Content-Length',0))
            if not 0<size<=1000000:raise ValueError('Extra options data is missing or too large.')
            data=json.loads(h.rfile.read(size))
        result=operation(h.server.store,str(uuid.UUID(m[1])),action,data)
        h.respond(200,result) if result is not None else h.respond(404,{'error':'Flow not found.'})
    except (ValueError,UnicodeDecodeError) as e:h.respond(400,{'error':str(e)})
    except psycopg.Error:h.respond(503,{'error':'Extra options could not be loaded or saved. Keep your edits and retry.'})
    return True
