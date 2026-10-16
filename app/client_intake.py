"""Bounded, values-only Google Sheets XLSX intake. Never updates an existing event."""
import base64, binascii, io, json, posixpath, re, uuid, zipfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET
from urllib.parse import urlsplit
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
HEADERS={
 'Event':['Field','Value','Guidance'],
 'Categories':['Name','Price'],
 'Sessions':['Title','Date','Start time','End time','Location','Track','Speaker','Description','Price','Capacity'],
 'Additional options':['Name','Description','Kind','Price','Inventory','Multiple','Taxable'],
 'Branding':['Field','Value','Guidance'],
 'Confirmation':['Field','Value','Guidance'],
}
KEYS={
 'Event':['name','start','end','timezone','format','venue','location','url','description','organizer','email','currency'],
 'Branding':['title','about','font','background_color','title_color','body_color'],
 'Confirmation':['heading','message'],
}
LIMIT=4*1024*1024

def workbook(raw):
    if not raw or len(raw)>LIMIT:raise ValueError('Choose an XLSX file smaller than 4 MB.')
    try:
        z=zipfile.ZipFile(io.BytesIO(raw));infos=z.infolist()
        if len(infos)>200 or sum(i.file_size for i in infos)>12*1024*1024:raise ValueError('The workbook is too large after unpacking.')
        if len({i.filename for i in infos})!=len(infos):raise ValueError('Duplicate workbook parts are not supported.')
        if any('vba' in i.filename.lower() or 'externallinks' in i.filename.lower() or i.flag_bits&1 for i in infos):raise ValueError('Remove macros, external links and encryption before uploading.')
        def xml(name):
            data=z.read(name)
            if b'\x00' in data or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('Unsupported XML declarations.')
            return ET.fromstring(data)
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(n.itertext()) for n in xml('xl/sharedStrings.xml').findall('s:si',NS)]
        rels={r.attrib['Id']:r.attrib for r in xml('xl/_rels/workbook.xml.rels')}
        result={}
        for sheet in xml('xl/workbook.xml').findall('s:sheets/s:sheet',NS):
            name=sheet.attrib['name']
            if name=='Start here':continue
            if name not in HEADERS or name in result:raise ValueError('Use the original template tabs; unexpected tab: '+name)
            relation=rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            if relation.get('TargetMode')=='External':raise ValueError('External sheets are not supported.')
            target=relation['Target'];path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            if not path.startswith('xl/worksheets/'):raise ValueError('Unsupported sheet location.')
            rows=[];last_row=0
            for row in xml(path).findall('s:sheetData/s:row',NS):
                number=int(row.attrib['r'])
                if number<=last_row:raise ValueError('Rows must be unique and ordered.')
                last_row=number
                if number>502:raise ValueError(name+': use at most 500 data rows.')
                cells={}
                for cell in row.findall('s:c',NS):
                    ref=cell.attrib.get('r','');match=re.fullmatch(r'([A-Z]{1,2})([0-9]+)',ref)
                    if not match or int(match[2])!=number:raise ValueError('Invalid cell reference.')
                    col=0
                    for char in match[1]:col=col*26+ord(char)-64
                    if cell.find('s:f',NS) is not None:raise ValueError(name+' '+ref+': paste values only; formulas are not imported.')
                    if col>len(HEADERS[name]):
                        if cell.find('s:v',NS) is not None or cell.find('s:is',NS) is not None:raise ValueError(name+': remove extra columns.')
                        continue
                    if cell.find('s:f',NS) is not None:raise ValueError(name+' '+ref+': paste values only; formulas are not imported.')
                    kind=cell.attrib.get('t','');value=cell.findtext('s:v','',NS)
                    if kind=='s':value=shared[int(value)]
                    elif kind=='inlineStr':
                        node=cell.find('s:is',NS)
                        if node is None:raise ValueError('A workbook text cell is malformed.')
                        value=''.join(node.itertext())
                    elif kind in ('e','b'):raise ValueError(name+' '+ref+': use plain text, not errors or boolean cells.')
                    if len(value)>10000:raise ValueError(name+' '+ref+': text is too long.')
                    if col in cells:raise ValueError('Duplicate cell reference.')
                    cells[col]=value.strip()
                if any(cells.values()):rows.append((number,[cells.get(c,'') for c in range(1,len(HEADERS[name])+1)]))
            if not rows or rows[0]!=(1,HEADERS[name]):raise ValueError(name+': keep the template header row unchanged.')
            result[name]=rows[1:]
        if set(result)!=set(HEADERS):raise ValueError('Include all six template data tabs, even when optional tabs are empty.')
        return result
    except (zipfile.BadZipFile,KeyError,IndexError,ET.ParseError,TypeError,OverflowError) as exc:
        raise ValueError('This file is not a supported XLSX workbook. Export the template from Google Sheets as Microsoft Excel (.xlsx).') from exc

def normalize(tabs):
    from server import validate as event_validate
    from registration import starter,validate_page,CURRENCIES
    from sessions import validate as session_validate
    from extra_options import validate as extras_validate
    from welcome import validate as welcome_validate
    from confirmation import validate as confirmation_validate
    errors=[]
    def keyed(name):
        result={}
        for row,values in tabs[name]:
            key,value=values[:2]
            if key not in KEYS[name] or key in result:errors.append(f'{name} row {row}: unknown or repeated field {key}.')
            else:result[key]=value
        return result
    event=keyed('Event');branding=keyed('Branding');confirmation=keyed('Confirmation')
    currency=event.pop('currency','') or 'USD'
    def checked(label,fn,default):
        try:return fn()
        except (ValueError,InvalidOperation) as exc:errors.append(label+': '+str(exc));return default
    event=checked('Event',lambda:event_validate(event),None)
    if currency not in CURRENCIES:errors.append('Event: currency must be USD, EUR, GBP, CAD, AUD or JPY.')
    def price(value):
        try:n=Decimal(value)
        except InvalidOperation:raise ValueError('Enter a price such as 25.00, without currency symbols.')
        factor=10**CURRENCIES.get(currency,2);minor=n*factor
        if not n.is_finite() or minor!=minor.to_integral_value() or not 0<=minor<=99999999:raise ValueError('Price has unsupported decimals or is outside the allowed range.')
        return int(minor)
    def stock(value):
        if not value:return None
        if not re.fullmatch(r'\d{1,7}',value) or int(value)>1000000:raise ValueError('Capacity/inventory must be a whole number up to 1,000,000, or blank.')
        return int(value)
    def flag(value):
        if value.lower() not in ('yes','no',''):raise ValueError('Use Yes or No.')
        return value.lower()=='yes'
    def rows(name,fn):
        out=[];names=set()
        for number,values in tabs[name]:
            if values[0].casefold() in names:errors.append(f'{name} row {number}: duplicate name/title.');continue
            names.add(values[0].casefold())
            item=checked(f'{name} row {number}',lambda:fn(values),None)
            if item is not None:out.append(item)
        return out
    ident=lambda value:str(uuid.uuid5(uuid.NAMESPACE_URL,'regfire-intake:'+value))
    categories=rows('Categories',lambda v:dict(id=ident('category:'+v[0]),name=v[0],price_minor=price(v[1])))
    sessions=rows('Sessions',lambda v:dict(id=ident('session:'+v[0]),title=v[0],date=v[1],start_time=v[2],end_time=v[3],start=v[1]+'T'+v[2],end=v[1]+'T'+v[3],location=v[4],track=v[5],speaker=v[6],description=v[7],price_minor=price(v[8] or '0'),capacity=stock(v[9])))
    extras=rows('Additional options',lambda v:dict(id=ident('item:'+v[0]),name=v[0],description=v[1],kind=v[2] or 'physical',price_minor=price(v[3]),inventory=stock(v[4]),allow_multiple=flag(v[5]),taxable=flag(v[6])))
    result={'event':event}
    if event:
        result['registration']=checked('Categories',lambda:validate_page(starter(event|{'id':''})|{'currency':currency,'regtypes':categories},event['timezone']),None)
        result['sessions']=checked('Sessions',lambda:session_validate({'currency':currency,'sessions':sessions},event),None)
        for row in sessions:
            stamp=row['date']+'T'+row['start_time']
            end=row['date']+'T'+row['end_time']
            if event['start'] and stamp<event['start'] or event['end'] and end>event['end']:errors.append('Sessions: '+row['title']+' is outside the event dates.')
    result['extras']=checked('Additional options',lambda:extras_validate({'currency':currency,'items':extras}),None)
    welcome={k:v for k,v in branding.items() if v and k in ('title','about','background_color','title_color')}
    welcome.update(title_font=branding.get('font') or 'default',about_font=branding.get('font') or 'default',about_color=branding.get('body_color') or '#24242a',background_mode='color')
    result['welcome']=checked('Branding',lambda:welcome_validate(welcome),None)
    result['confirmation']=checked('Confirmation',lambda:confirmation_validate({k:v for k,v in confirmation.items() if v}),None)
    if errors:raise ValueError('\n'.join(errors[:30]))
    return result

def table(store,name):return sql.Identifier(store.schema,name)

def preview(store,user_id,raw):
    data=normalize(workbook(raw));token=str(uuid.uuid4())
    with store.connect() as c:
        c.execute(sql.SQL('DELETE FROM {} WHERE expires<now()').format(table(store,'client_intake_previews')))
        c.execute(sql.SQL('INSERT INTO {}(id,user_id,body) VALUES(%s,%s,%s)').format(table(store,'client_intake_previews')),(token,user_id,Jsonb(data)))
    return {'token':token,'draft':data,'expires_minutes':30}

def apply(store,user_id,token):
    token=str(uuid.UUID(token))
    with store.connect() as c:
        row=c.execute(sql.SQL('SELECT body,event_id,expires>now() FROM {} WHERE id=%s AND user_id=%s FOR UPDATE').format(table(store,'client_intake_previews')),(token,user_id)).fetchone()
        if not row or not row[2]:raise ValueError('This review expired or is unavailable. Upload the workbook again.')
        if row[1]:return {'event_id':str(row[1]),'already_applied':True}
        data=row[0];eid=str(uuid.uuid4());now=datetime.now(timezone.utc).isoformat()
        event=data['event']|{'id':eid,'status':'draft','created':now,'updated':now}
        c.execute(sql.SQL('INSERT INTO {}(id,body,updated) VALUES(%s,%s,%s)').format(store.table()),(eid,Jsonb(event),now))
        c.execute(sql.SQL('INSERT INTO {}(user_id,event_id) VALUES(%s,%s)').format(table(store,'access_event_grants')),(user_id,eid))
        c.execute(sql.SQL("INSERT INTO {}(id,event_id,name,kind,position) VALUES(%s,%s,'Attendee','attendee',0)").format(table(store,'registration_flows')),(eid,eid))
        for key,name in [('registration','registration_pages'),('welcome','welcome_pages'),('sessions','event_sessions'),('extras','extra_options'),('confirmation','confirmation_pages')]:
            body=data[key]|{'event_id':eid,'status':'draft','updated':now}
            if key in ('registration','welcome'):
                c.execute(sql.SQL('INSERT INTO {}(event_id,body,updated) VALUES(%s,%s,%s)').format(table(store,name)),(eid,Jsonb(body),now))
            else:c.execute(sql.SQL('INSERT INTO {}(event_id,body,revision) VALUES(%s,%s,1)').format(table(store,name)),(eid,Jsonb(body)))
        c.execute(sql.SQL('UPDATE {} SET event_id=%s WHERE id=%s').format(table(store,'client_intake_previews')),(eid,token))
    return {'event_id':eid,'already_applied':False}

def handle(h):
    path=urlsplit(h.path).path
    if path not in ('/api/client-intake/preview','/api/client-intake/apply'):return False
    try:
        size=int(h.headers.get('Content-Length',0))
        if not 0<size<=6*1024*1024:raise ValueError('Choose a workbook smaller than 4 MB.')
        data=json.loads(h.rfile.read(size))
        if not isinstance(data,dict):raise ValueError('Send an intake request.')
        if path.endswith('/preview'):
            encoded=data.get('file','')
            if not isinstance(encoded,str):raise ValueError('Choose an XLSX workbook.')
            result=preview(h.server.store,h.identity['id'],base64.b64decode(encoded,validate=True))
        else:result=apply(h.server.store,h.identity['id'],data.get('token',''))
        h.respond(200,result)
    except (ValueError,UnicodeError,binascii.Error,AttributeError) as exc:h.respond(400,{'error':str(exc)})
    except psycopg.Error:h.respond(503,{'error':'The intake could not be saved. No partial event was applied. Keep this page open and retry.'})
    return True
