"""Pure confirmation email presentation; rendering never sends or fetches assets."""
from html import escape
from urllib.parse import urlsplit, quote
from confirmation_pdf import display, money


def render(doc, images=None, confirmation_url=None):
 """Return email HTML. Image mappings contain trusted CID names, never paths/URLs."""
 images=images or {}
 def text(value):return escape(display(value),quote=True)
 def image(key,alt,width):
  cid=images.get(key,'')
  if not cid:return ''
  import re
  if not re.fullmatch(r'[A-Za-z0-9_.-]+',cid):raise ValueError('Use a safe inline image identifier.')
  return f'<img src="cid:{cid}" alt="{text(alt)}" width="{width}" style="display:block;max-width:100%;height:auto;border:0">'
 def para(value,small=False):return '<p style="margin:4px 0;'+('font-size:12px;color:#62636e;' if small else '')+'">'+text(value).replace('\n','<br>')+'</p>'
 def heading(value):return '<h2 style="font-size:19px;font-weight:500;margin:14px 0 6px">'+text(value)+'</h2>'
 s=doc['settings'];q=doc['quote'];e=doc['event'];currency=q['currency']
 qr='<div style="padding:8px 0;text-align:center;max-width:240px;margin:0 auto">'+'<div style="width:156px;margin:0 auto">'+image('qr','QR containing event and confirmation IDs',156)+'</div>'+'<p style="margin:6px 0 0;font-size:12px;line-height:1.4;overflow-wrap:anywhere"><strong>'+text(doc.get('confirmation_number',doc['confirmation_id']))+'</strong></p></div>'
 if s['show_wallet']:
  qr+='<table role="presentation" style="width:100%;max-width:240px;margin:0 auto" aria-label="Wallet badges; passes are not available"><tr>'
  for kind,label in [('apple','Add to Apple Wallet'),('google','Add to Google Wallet')]:
   qr+='<td style="width:50%;padding:4px;vertical-align:middle">'+image(kind+'-wallet',label+' — unavailable',110)+'</td>'
  qr+='</tr></table>'
 notice='SAMPLE - Fictional attendee and transaction. Not valid for entry.' if doc['sample'] else 'SANDBOX TEST - No live payment.' if doc['sandbox'] else 'Payment confirmed' if doc['status']=='paid' else 'Free registration confirmed - No payment required.'
 body='<table role="presentation" width="100%"><tr><td class="stack" width="105" style="vertical-align:middle">'+image('logo','Event logo',85)+'</td><td class="stack">'+para('REGISTRATION CONFIRMATION',True)+'<h1 style="font-size:28px;font-weight:500;margin:8px 0">'+text(s['heading'])+'</h1>'+para('Registration. Reignited.',True)+'</td></tr></table>'
 body+='<div style="background:#fff2e9;padding:8px;margin-top:16px">'+text(notice)+'</div>'+heading(e['name'])+para(' | '.join(str(e.get(k,'')) for k in ('start','end','timezone') if e.get(k)))+para(' | '.join(str(e.get(k,'')) for k in ('venue','location') if e.get(k)))
 if s['qr_position']=='top':body+=qr
 for block in s['layout']:
  if block=='message':body+=para(s['message'])
  elif block=='attendee':
   attendee=heading('Attendee')+para(q['regtype'])+''.join(para(d['label']+': '+display(d['value'])) for d in q['details'] if d['value'] not in ('',None))
   if s['qr_position'] in ('left','right'):
    cells=[attendee,qr] if s['qr_position']=='right' else [qr,attendee]
    body+='<table role="presentation" width="100%"><tr>'+''.join('<td class="stack" style="vertical-align:top;width:'+('36%' if c==qr else '64%')+';padding:0 8px 8px 0">'+c+'</td>' for c in cells)+'</tr></table>'
   else:body+=attendee
  elif block=='receipt':
   body+=heading('Receipt preview' if doc['sample'] else 'Receipt')+'<table class="receipt" width="100%" style="border-collapse:collapse;font-size:13px"><thead><tr>' + ''.join('<th align="left" style="background:#f2f2f5;padding:8px;font-weight:400">'+x+'</th>' for x in ['ITEM','QTY','UNIT','AMOUNT'])+'</tr></thead><tbody>'
   for line in q['lines']:
    body+='<tr>'+''.join('<td style="padding:8px;vertical-align:top">'+text(v)+'</td>' for v in [line['name'],line['quantity'],money(line['unit_price_minor'],currency),money(line['line_total_minor'],currency)])+'</tr>'
   body+='</tbody></table><table width="100%" style="border-top:1px solid #dddddf">'
   for label,value in [('Subtotal',q['subtotal_minor']),('Discount',-q['discount_minor']),('Tax',q['tax_minor']),('Grand total',q['grand_total_minor']),('Sample amount (not a payment)' if doc['sample'] else 'Sandbox amount (not a live payment)' if doc['sandbox'] else 'Amount paid',q['grand_total_minor'] if doc['sample'] else doc['paid_minor'])]:
    body+='<tr><td>'+text(label)+'</td><td align="right">'+text(money(value,currency))+'</td></tr>'
   body+='</table>'
  elif block=='sessions' and s['show_sessions'] and q['sessions']:
   body+=heading('Your registered sessions')
   for row in q['sessions']:body+=para(row['title'])+para(' | '.join(str(row.get(k,'')) for k in ('start','end','location') if row.get(k)),True)
  elif block=='extras' and s['show_extras']:
   lines=[l for l in q['lines'] if l['kind']=='extra']
   if lines:body+=heading('Your additional options')+''.join(para(str(l['quantity'])+' × '+l['name']+' — '+money(l['line_total_minor'],currency)) for l in lines)
  elif block=='sponsors' and s['show_sponsors'] and s['sponsors']:
   body+=heading('Our sponsors')+'<table role="presentation" width="100%">'
   for start in range(0,len(s['sponsors']),3):
    body+='<tr>'+''.join('<td width="33%" style="padding:8px">'+(image('sponsor:'+l['asset_id'],l['name'],150) or para(l['name']))+'</td>' for l in s['sponsors'][start:start+3])+'</tr>'
   body+='</table>'
 if s['qr_position']=='bottom':body+=qr
 if confirmation_url:
  u=urlsplit(confirmation_url)
  if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Use the public HTTPS confirmation link.')
  body+='<p style="margin:24px 0"><a href="'+text(confirmation_url)+'" style="color:#b6451c">View your secure confirmation and receipt</a></p>'
 base=''
 if confirmation_url:
  parsed=urlsplit(confirmation_url);base=parsed.scheme+'://'+parsed.netloc
 dashboard=base+'/registrant-login?event='+quote(doc['event_id'],safe='')
 if not base and doc.get('dashboard_url'):dashboard=doc['dashboard_url']
 body+='<div style="border-top:1px solid #ddd;margin-top:20px;padding:16px 0">'+para('Need to review your registration? Sign in to your attendee dashboard. You can correct contact details or start another registration there. Contact the organizer for session, purchase or payment changes.')+'<p style="margin:14px 0"><a target="_blank" rel="noopener" href="'+text(dashboard)+'" style="display:inline-block;background:#b6451c;color:#fff;text-decoration:none;padding:12px 18px;border-radius:6px;font-weight:bold">Sign in to your dashboard</a></p></div>'
 if s['show_wallet']:body+=para('Wallet badges are previews only. Passes are not available yet.',True)
 body+=para('RegFire | Registration. Reignited.',True)
 return '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><style>@media(max-width:480px){.stack{display:block!important;width:100%!important;padding:0!important}h1{font-size:22px!important}.email-shell{padding:12px!important}table{table-layout:fixed}td,th{overflow-wrap:anywhere}.receipt{font-size:11px!important}.receipt td,.receipt th{padding:5px 2px!important}.receipt th:first-child{width:38%}.receipt th:nth-child(2){width:10%}.receipt th:nth-child(3),.receipt th:nth-child(4){width:26%}}</style></head><body style="margin:0;background:#fff;color:#24242b;font:14px/1.45 Arial,sans-serif"><table role="presentation" width="100%" style="border-top:8px solid #b6451c"><tr><td class="email-shell" style="padding:24px"><div style="max-width:700px;margin:auto">'+body+'</div></td></tr></table></body></html>'


def prepare(doc, store, upload_root, confirmation_url=None):
 """Assemble bounded inline PNGs from flow-owned assets; never fetch remote URLs."""
 import io
 from pathlib import Path
 from PIL import Image,ImageOps
 from confirmation import qr_png
 root=Path(upload_root).resolve()
 images={'qr':'confirmation-qr'}
 attachments=[dict(content_id='confirmation-qr',data=qr_png(doc['event_id'],doc['confirmation_id']))]
 def attach(key,cid,path):
  with Image.open(path) as source:
   if source.width*source.height>25_000_000:raise ValueError('Confirmation image is too large.')
   source.seek(0)
   normalized=ImageOps.exif_transpose(source).convert('RGBA')
   normalized.thumbnail((900,450))
   out=io.BytesIO();normalized.save(out,format='PNG')
  if sum(len(a['data']) for a in attachments)+len(out.getvalue())>5*1024*1024:raise ValueError('Confirmation images exceed the email size limit.')
  images[key]=cid;attachments.append(dict(content_id=cid,data=out.getvalue()))
 def owned(ident):
  row=store.asset(doc['flow_id'],ident)
  if not row:raise ValueError('Confirmation image does not belong to this flow.')
  path=(root/row[0]).resolve()
  if not path.is_relative_to(root) or not path.is_file():raise ValueError('Confirmation image is unavailable.')
  return path
 logo=doc.get('appearance',{}).get('logo_asset_id')
 attach('logo','event-logo',owned(logo) if logo else Path(__file__).parent/'static/regfire-logo-3d-transparent.png')
 if doc['settings']['show_wallet']:
  attach('apple-wallet','apple-wallet-preview',Path(__file__).parent/'static/apple-wallet-official.png')
  attach('google-wallet','google-wallet-preview',Path(__file__).parent/'static/google-wallet-official.png')
 if doc['settings']['show_sponsors']:
  for i,sponsor in enumerate(doc['settings']['sponsors']):
   attach('sponsor:'+sponsor['asset_id'],'sponsor-'+str(i),owned(sponsor['asset_id']))
 return dict(html=render(doc,images,confirmation_url),inline_images=attachments)
