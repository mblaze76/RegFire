"""Flow-specific confirmation presentation. All receipts derive from saved server orders."""
import copy,json,re,uuid,io
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlsplit
from psycopg import sql
from psycopg.types.json import Jsonb
import psycopg
from access import AccessError
BLOCKS=['sponsors','message','attendee','receipt','sessions','extras']
DEFAULT=dict(heading='Your event, all in one place.',message='Thank you for registering. We look forward to seeing you.',layout=BLOCKS,qr_position='right',show_sessions=True,show_extras=True,show_sponsors=True,show_wallet=True,sponsors=[])
def validate(data):
 if not isinstance(data,dict):raise ValueError('Send confirmation settings.')
 out=copy.deepcopy(DEFAULT)
 for k,limit in [('heading',160),('message',2000)]:
  v=data.get(k,out[k])
  if not isinstance(v,str) or len(v)>limit or (k=='heading' and not v.strip()):raise ValueError('Check confirmation '+k+'.')
  out[k]=v.strip()
 layout=data.get('layout',BLOCKS)
 if not isinstance(layout,list) or len(layout)!=len(BLOCKS) or any(not isinstance(x,str) for x in layout) or set(layout)!=set(BLOCKS):raise ValueError('Keep each confirmation section exactly once.')
 out['layout']=layout[:]
 pos=data.get('qr_position','right')
 if pos not in ('left','right','top','bottom'):raise ValueError('Choose a QR placement.')
 out['qr_position']=pos
 for k in ('show_sessions','show_extras','show_sponsors','show_wallet'):
  v=data.get(k,True)
  if type(v) is not bool:raise ValueError('Choose on or off for display sections.')
  out[k]=v
 logos=data.get('sponsors',[])
 if not isinstance(logos,list) or len(logos)>12:raise ValueError('Use up to twelve sponsor logos.')
 out['sponsors']=[]
 for row in logos:
  if not isinstance(row,dict):raise ValueError('Check sponsor logo.')
  ident=str(uuid.UUID(row.get('asset_id','')));name=row.get('name','Sponsor')
  if not isinstance(name,str) or len(name)>100:raise ValueError('Use a short sponsor name.')
  if ident in [x['asset_id'] for x in out['sponsors']]:raise ValueError('A sponsor logo is listed twice.')
  out['sponsors'].append(dict(asset_id=ident,name=name))
 return out

def operation(store,flow,data=None):
 from publication_snapshot import page as published_page
 published=published_page(store,flow,'confirmation_pages') if data is None else None
 if published is not None:return published
 table=sql.Identifier(store.schema,'confirmation_pages')
 with store.connect() as c:
  event=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s FOR UPDATE').format(store.table()),(flow,)).fetchone()
  if not event or not c.execute(sql.SQL('SELECT 1 FROM {} WHERE id=%s AND NOT archived').format(sql.Identifier(store.schema,'registration_flows')),(flow,)).fetchone():return None
  row=c.execute(sql.SQL('SELECT body,revision FROM {} WHERE event_id=%s').format(table),(flow,)).fetchone();page=validate(row[0] if row else {});revision=row[1] if row else 0
  if data is not None:
   if type(data.get('revision')) is not int or data['revision']!=revision:raise ValueError('Confirmation changed in another tab. Reload before saving; your edits are still here.')
   page=validate(data)
   for logo in page['sponsors']:
    if not c.execute(sql.SQL('SELECT 1 FROM {} WHERE event_id=%s AND id=%s').format(sql.Identifier(store.schema,'registration_assets')),(flow,logo['asset_id'])).fetchone():raise ValueError('Use a logo uploaded to this registration flow.')
   revision+=1;c.execute(sql.SQL('INSERT INTO {}(event_id,body,revision) VALUES(%s,%s,%s) ON CONFLICT(event_id) DO UPDATE SET body=excluded.body,revision=excluded.revision').format(table),(flow,Jsonb(page),revision))
  return page|dict(revision=revision,event_id=flow)

def qr_payload(event_id,confirmation_id):return json.dumps(dict(event_id=event_id,confirmation_id=confirmation_id),separators=(',',':'))
def qr_svg(payload):
 from reportlab.graphics.barcode.qr import QrCodeWidget
 from reportlab.graphics.shapes import Drawing
 from reportlab.graphics import renderSVG
 q=QrCodeWidget(payload,barLevel='M',barBorder=4);x,y,w,h=q.getBounds();d=Drawing(w,h);d.add(q);return renderSVG.drawToString(d)

def qr_png(event_id,confirmation_id):
 """Email-safe QR artwork: identifiers only, integer pixels and a quiet zone."""
 from reportlab.graphics.barcode.qr import QrCodeWidget
 from PIL import Image,ImageDraw
 q=QrCodeWidget(qr_payload(event_id,confirmation_id),barLevel='M')
 q.qr.make()
 modules=q.qr.modules;scale=6;border=4
 image=Image.new('RGB',((len(modules)+2*border)*scale,)*2,'white')
 draw=ImageDraw.Draw(image)
 for y,row in enumerate(modules):
  for x,dark in enumerate(row):
   if dark:
    left=(x+border)*scale;top=(y+border)*scale
    draw.rectangle((left,top,left+scale-1,top+scale-1),fill='black')
 output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()

def date_label(value,zone):
 try:return datetime.fromisoformat(value).replace(tzinfo=ZoneInfo(zone)).strftime('%b %d, %Y, %I:%M %p %Z')
 except (ValueError,TypeError):return value

def document(store,flow,order=None,page=None):
 from publication_snapshot import current,load,using
 if order is not None and current(store,flow) is None:
  snapshot=load(store,flow,include_unpublished=True)
  if snapshot:
   with using(store,flow,snapshot):return document(store,flow,order,page)
 page=page or operation(store,flow)
 if not page:raise ValueError('Flow not found.')
 with store.connect() as c:
  event=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()),(flow,)).fetchone()[0]
  branding=c.execute(sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(sql.Identifier(store.schema,'registration_pages')),(flow,)).fetchone()
 from publication_snapshot import current
 snap=current(store,flow)
 if snap:event=snap['event'];branding=(snap['registration_pages'],)
 from event_theme import apply as apply_event_theme
 appearance=apply_event_theme(store,event | {'id':flow},branding[0] if branding else {})['appearance']
 sample=order is None
 if sample:
  quote=dict(currency='USD',regtype='Attendee one-day pass',details=[dict(label='Name',value='Jordan Sample'),dict(label='Company',value='Sample Event Company'),dict(label='Email',value='jordan.sample@example.com')],sessions=[dict(title='Opening keynote: Registration. Reignited.',start='9:00 AM',end='10:00 AM',location='Main Hall'),dict(title='Building a better onsite experience',start='1:00 PM',end='2:00 PM',location='Room 201')],lines=[dict(name='Attendee one-day pass',quantity=1,unit_price_minor=29500,line_total_minor=29500,kind='registration'),dict(name='Conference tote',quantity=1,unit_price_minor=2500,line_total_minor=2500,kind='extra'),dict(name='Networking reception',quantity=1,unit_price_minor=4500,line_total_minor=4500,kind='extra')],subtotal_minor=36500,discount_minor=0,tax_minor=0,grand_total_minor=36500)
  ident='SAMPLE-RF-2026-00482';status='sample';paid=0;public_number='12345678'
 else:
  if order['flow_id']!=flow:raise ValueError('Order does not belong to this flow.')
  if order['status'] not in ('paid','confirmed_free'):raise ValueError('Confirmation is available after verified payment or free registration completion.')
  quote=copy.deepcopy(order['quote']);ident=order['id'];status=order['status'];paid=quote['grand_total_minor'] if status=='paid' else 0
  from confirmation_numbers import number
  public_number=number(store,ident)
 event_id=event.get('parent_event_id',flow);payload=qr_payload(event_id,ident)
 for session in quote['sessions']:
  for key in ('start','end'):session[key]=date_label(session.get(key,''),event.get('timezone','UTC'))
 event=copy.deepcopy(event)
 for key in ('start','end'):event[key]=date_label(event.get(key,''),event.get('timezone','UTC'))
 return dict(settings=page,event={k:event.get(k,'') for k in ('name','start','end','timezone','venue','location')},event_id=event_id,flow_id=flow,confirmation_id=ident,confirmation_number=public_number,sample=sample,status=status,sandbox=bool(order and order.get('mode')=='sandbox'),paid_minor=paid,quote=quote,qr_payload=payload,qr_svg=qr_svg(payload),appearance=appearance,wallet=dict(apple=None,google=None,message='Wallet passes are not configured.'))

def send_bytes(h,content,mime,filename=None):
 h.send_response(200);h.send_header('Content-Type',mime);h.send_header('Content-Length',str(len(content)));h.send_header('Cache-Control','no-store');h.send_header('X-Content-Type-Options','nosniff')
 if filename:h.send_header('Content-Disposition','attachment; filename="'+filename+'"')
 h.end_headers();h.wfile.write(content)
def handle(h):
 path=urlsplit(h.path).path
 lookup_match=re.fullmatch(r'/api/events/([a-f0-9-]{36})/confirmation/lookup/([a-f0-9-]+)',path)
 if lookup_match:
  if h.command!='GET':h.respond(405,dict(error='Use GET.'));return True
  try:
   # access_http has already required organizer identity, product and event grants.
   from confirmation_numbers import lookup
   order=lookup(h.server.store,lookup_match[1],lookup_match[2])
   if not order:h.respond(404,dict(error='Registration not found.'));return True
   h.respond(200,document(h.server.store,lookup_match[1],order));return True
  except (ValueError,TypeError):h.respond(400,dict(error='Invalid confirmation reference.'))
  except psycopg.Error:h.respond(503,dict(error='Confirmation lookup temporarily unavailable.'))
  return True
 files={'/apple-wallet-official.svg':'image/svg+xml','/apple-wallet-official.png':'image/png','/google-wallet-official.svg':'image/svg+xml','/google-wallet-official.png':'image/png','/confirmation-preview.js':'text/javascript','/confirmation-common.js':'text/javascript','/confirmation-builder.js':'text/javascript','/confirmation.css':'text/css','/confirmation-preview':'text/html'}
 if path in files and h.command=='GET':
  name='confirmation-preview.html' if path=='/confirmation-preview' else path[1:];send_bytes(h,(Path(__file__).parent/'static'/name).read_bytes(),files[path]);return True
 m=re.fullmatch(r'/api/events/([a-f0-9-]{36})/confirmation(?:/(preview|email-preview|sample.pdf))?',path);o=re.fullmatch(r'/api/checkout/([a-f0-9-]{36})/confirmation(?:/(receipt.pdf|apple.pkpass|google))?',path)
 if not(m or o):return False
 try:
  store=h.server.store
  if m:
   if h.command not in ('GET','PUT','POST'):raise ValueError('Use GET, PUT or POST.')
   data=None
   if h.command!='GET':
    size=int(h.headers.get('Content-Length',0))
    if not 0<size<=64000:raise ValueError('Confirmation settings are missing or too large.')
    data=json.loads(h.rfile.read(size))
   if not m[2]:
    if h.command=='POST':raise ValueError('Use PUT to save.')
    result=operation(store,m[1],data);h.respond(200,result) if result else h.respond(404,dict(error='Flow not found.'));return True
   page=operation(store,m[1]);page=(validate(data)|dict(event_id=m[1])) if data is not None else page
   # Preview references are subject to the same asset boundary as saved settings.
   for logo in (page or {}).get('sponsors',[]):
    if not store.asset(m[1],logo['asset_id']):raise ValueError('Use a logo from this flow.')
   doc=document(store,m[1],page=page)
  else:
   if h.command!='GET':raise ValueError('Use GET.')
   from checkout import get_order
   with store.connect() as c:order=get_order(c,store,o[1],h.identity['id'])
   doc=document(store,order['flow_id'],order)
   import wallet
   config=wallet.settings(h.server).read()
   from communications import settings_for
   origin=settings_for(h.server).read().get('public_url','')
   if doc['settings']['show_wallet'] and not doc['sandbox']:
    if not wallet.issues('apple',config['apple']) and origin.startswith('https://'):
     doc['wallet']['apple']=origin+'/api/checkout/'+order['id']+'/confirmation/apple.pkpass'
    if not wallet.issues('google',config['google']):doc['wallet']['google']=wallet.google_url(doc,config['google'])
    if doc['wallet']['apple'] or doc['wallet']['google']:doc['wallet']['message']='Open on your device to save your pass. Sign in to RegFire if prompted.'
   if o[2]=='apple.pkpass':
    if not doc['settings']['show_wallet'] or not doc['wallet']['apple']:raise ValueError('Apple Wallet is unavailable for this confirmation.')
    send_bytes(h,wallet.apple_pass(doc,config['apple']),'application/vnd.apple.pkpass','RegFire.pkpass');return True
   if o[2]=='google':
    if not doc['wallet']['google']:raise ValueError('Google Wallet is unavailable for this confirmation.')
    h.respond(200,dict(url=doc['wallet']['google']));return True
  from deployment_config import DeploymentConfig
  doc['dashboard_url']=DeploymentConfig.load(h.server.server_port).origin+'/registrant-login?event='+doc['event_id']
  if m and m[2]=='email-preview':
   import base64
   from confirmation_email import prepare
   email=prepare(doc,store,getattr(h.server,'upload_root',Path(__file__).parent/'uploads'))
   html=email['html']
   for item in email['inline_images']:
    html=html.replace('cid:'+item['content_id']+'"','data:image/png;base64,'+base64.b64encode(item['data']).decode()+'"')
   h.respond(200,dict(html=html,sample=True));return True
  if (m and m[2]=='sample.pdf') or (o and o[2]):
   from confirmation_pdf import render
   content=render(doc,store,getattr(h.server,'upload_root',Path(__file__).parent/'uploads'));send_bytes(h,content,'application/pdf','RegFire_Confirmation_SAMPLE.pdf' if doc['sample'] else 'RegFire_Confirmation.pdf')
  else:h.respond(200,doc)
 except AccessError as e:h.respond(e.status,dict(error=str(e)))
 except (ValueError,TypeError,AttributeError,UnicodeDecodeError) as e:h.respond(400,dict(error=str(e)))
 except psycopg.Error:h.respond(503,dict(error='Confirmation storage is unavailable. Keep your edits and retry.'))
 return True
