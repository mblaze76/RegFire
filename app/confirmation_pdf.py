"""Paginated confirmation PDF using the same saved block order as the live preview."""
import io
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,KeepTogether
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from PIL import Image as PILImage

ROOT=Path(__file__).parent
INK=colors.HexColor('#24242b');ORANGE=colors.HexColor('#b6451c');GRAY=colors.HexColor('#62636e')
def display(value):
 if isinstance(value,dict):return ', '.join(str(v) for v in value.values() if v)
 if isinstance(value,list):return ', '.join(map(str,value))
 if isinstance(value,bool):return 'Yes' if value else 'No'
 return str(value) if value is not None else ''
def money(v,c):return c+' '+(f'{v:,.0f}' if c=='JPY' else f'{v/100:,.2f}')
def render(doc,store,upload_root):
 styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='RFIdentifier',fontName='Helvetica-Bold',fontSize=8,leading=11,textColor=INK,alignment=1,spaceAfter=7,wordWrap='CJK'));styles.add(ParagraphStyle(name='RFButton',fontName='Helvetica-Bold',fontSize=10,leading=14,textColor=colors.white,alignment=1));styles.add(ParagraphStyle(name='RFBody',fontName='Helvetica',fontSize=9,leading=11,textColor=INK,spaceAfter=3,wordWrap='CJK'));styles.add(ParagraphStyle(name='RFSmall',parent=styles['RFBody'],fontSize=7,leading=9,textColor=GRAY));styles.add(ParagraphStyle(name='RFTitle',parent=styles['RFBody'],fontName='Helvetica-Bold',fontSize=19,leading=22,spaceAfter=6));styles.add(ParagraphStyle(name='RFSection',parent=styles['RFBody'],fontName='Helvetica-Bold',fontSize=12,leading=14,spaceBefore=6,spaceAfter=4))
 def p(text,style='RFBody'):return Paragraph(escape(display(text)).replace('\n','<br/>'),styles[style])
 def asset(ident,width=96,height=54):
  row=store.asset(doc['flow_id'],ident) if ident else None
  path=Path(upload_root)/row[0] if row else ROOT/'static/regfire-logo-3d-transparent.png'
  # Only server-owned asset records, never user-supplied filesystem paths or URLs.
  if not path.is_file():return p('Image unavailable','RFSmall')
  with PILImage.open(path) as im:w,h=im.size
  scale=min(width/w,height/h);return Image(str(path),width=w*scale,height=h*scale,hAlign='CENTER')
 settings=doc['settings'];q=doc['quote'];currency=q['currency'];event=doc['event'];story=[]
 logo=asset(doc.get('appearance',{}).get('logo_asset_id'),72,54)
 header=Table([[logo,[p('REGISTRATION CONFIRMATION','RFSmall'),p(settings['heading'],'RFTitle'),p('Registration. Reignited.','RFSmall')]]],colWidths=[105,435]);header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0)]));story+=[header,Spacer(1,3)]
 status='SAMPLE - Fictional attendee and transaction. Not valid for entry.' if doc['sample'] else 'SANDBOX TEST - No live payment.' if doc['sandbox'] else 'Payment confirmed' if doc['status']=='paid' else 'Free registration confirmed - No payment required.'
 notice=Table([[p(status)]],colWidths=[540]);notice.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#fff2e9')),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
 story += [notice,p(event['name'],'RFSection'),p(' | '.join(str(event.get(k,'')) for k in ('start','end','timezone') if event.get(k))),p(' | '.join(str(event.get(k,'')) for k in ('venue','location') if event.get(k)))]
 def qr():
  widget=QrCodeWidget(doc['qr_payload'],barLevel='M',barBorder=4);x,y,w,h=widget.getBounds();drawing=Drawing(96,96,transform=[96/w,0,0,96/h,0,0]);drawing.add(widget)
  drawing.hAlign='CENTER'
  rows=[drawing,p(doc.get('confirmation_number',doc['confirmation_id']),'RFIdentifier')]
  if settings['show_wallet']:
   badges=[]
   for kind in ('apple','google'):
    badge=ROOT/('static/'+kind+'-wallet-official.png')
    with PILImage.open(badge) as im:bw,bh=im.size
    badges.append(Image(str(badge),width=78,height=78*bh/bw,hAlign='CENTER'))
   pair=Table([badges],colWidths=[85,85]);pair.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER')]));rows.append(pair)
  return rows
 if settings['qr_position']=='top':story.append(KeepTogether(qr()))
 for block in settings['layout']:
  if block=='message':story.extend([p(settings['message'])] if settings['message'] else [])
  elif block=='attendee':
   rows=[p('Attendee','RFSection'),p(q['regtype'])]+[p(r['label']+': '+display(r['value'])) for r in q['details'] if r['value'] not in ('',None)]
   # Place QR beside a bounded header, letting long attendee detail lists flow onto later pages.
   if settings['qr_position'] in ('left','right'):
    cut=8 if sum(len(display(r['value'])) for r in q['details'][:6])<700 else 2;head=rows[:cut];tail=rows[cut:];cells=[head,qr()] if settings['qr_position']=='right' else [qr(),head];widths=[350,190] if settings['qr_position']=='right' else [190,350]
    t=Table([cells],colWidths=widths);t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),12),('ALIGN',(1 if settings['qr_position']=='right' else 0,0),(1 if settings['qr_position']=='right' else 0,0),'CENTER')]));story+=[t]+tail
   else:story+=rows
  elif block=='receipt':
   story.append(p('Receipt preview' if doc['sample'] else 'Receipt','RFSection'))
   rows=[[p(x,'RFSmall') for x in ('ITEM','QTY','UNIT','AMOUNT')]]
   for line in q['lines']:rows.append([p(line['name']),p(line['quantity']),p(money(line['unit_price_minor'],currency)),p(money(line['line_total_minor'],currency))])
   t=Table(rows,colWidths=[300,35,98,107],repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f2f2f5')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#dddddf')),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t)
   for label,v in [('Subtotal',q['subtotal_minor']),('Discount',-q['discount_minor']),('Tax',q['tax_minor']),('Grand total',q['grand_total_minor']),('Sample amount (not a payment)' if doc['sample'] else 'Sandbox amount (not a live payment)' if doc['sandbox'] else 'Amount paid',q['grand_total_minor'] if doc['sample'] else doc['paid_minor'])]:
    t=Table([[p(label),p(money(v,currency))]],colWidths=[400,140]);t.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]));story.append(t)
  elif block=='sessions' and settings['show_sessions'] and q['sessions']:
   story.append(p('Your registered sessions','RFSection'))
   for s in q['sessions']:story.append(KeepTogether([p(s['title']),p(' | '.join(str(s.get(k,'')) for k in ('start','end','location') if s.get(k)),'RFSmall')]))
  elif block=='extras' and settings['show_extras']:
   items=[l for l in q['lines'] if l.get('kind')=='extra']
   if items:story.append(p('Your additional options','RFSection'))
   for item in items:story.append(p(str(item['quantity'])+' × '+item['name']+' — '+money(item['line_total_minor'],currency)))
  elif block=='sponsors' and settings['show_sponsors']:
   logos=settings['sponsors']
   if logos:
    story.append(p('Our sponsors','RFSection'))
    for start in range(0,len(logos),3):
     cells=[[asset(s['asset_id'],145,42)] for s in logos[start:start+3]];cells += ['']*(3-len(cells));t=Table([cells],colWidths=[180]*3);t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER')]));story.append(t)
 if settings['qr_position']=='bottom':story.append(KeepTogether(qr()))
 story.append(p('Need to review your registration? Sign in to your attendee dashboard. You can correct contact details or start another registration there. Contact the organizer for session, purchase or payment changes.'))
 url=doc.get('dashboard_url','')
 if url:
  from urllib.parse import urlsplit
  u=urlsplit(url)
  if u.scheme not in ('https','http') or u.username or u.password or u.path!='/registrant-login':raise ValueError('Use the attendee dashboard URL.')
  button=Table([[Paragraph('<link href="'+escape(url,{'"':'&quot;'})+'">Sign in to your dashboard</link>',styles['RFButton'])]],colWidths=[190],hAlign='LEFT');button.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),ORANGE),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]));story.append(button)
 if settings['show_wallet']:story.append(p('Wallet badges are previews only. Passes are not available yet.','RFSmall'))
 def footer(canvas,pdf):
  canvas.setFillColor(ORANGE);canvas.rect(0,784,612,8,fill=1,stroke=0);canvas.setFont('Helvetica',8);canvas.setFillColor(GRAY);canvas.drawString(36,22,'RegFire | Registration. Reignited.');canvas.drawRightString(576,22,('SAMPLE / ' if doc['sample'] else '')+str(pdf.page))
 out=io.BytesIO();pdf=SimpleDocTemplate(out,pagesize=(612,792),leftMargin=36,rightMargin=36,topMargin=24,bottomMargin=36,title='RegFire registration confirmation');pdf.build(story,onFirstPage=footer,onLaterPages=footer);return out.getvalue()
