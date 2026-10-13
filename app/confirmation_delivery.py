"""Transactional confirmation outbox. Queueing never sends mail; dispatch is opt-in."""
import json,os,re
from psycopg import sql
from psycopg.types.json import Jsonb
from communications_providers import adapter_for,DeliveryError

def enqueue(c,store,order):
 if order['status'] not in ('paid','confirmed_free') or order.get('mode')=='sandbox':return
 # Resolve the actual configured email field, not a label or a user-provided recipient override.
 row=c.execute(sql.SQL('SELECT body FROM {} WHERE event_id=%s').format(sql.Identifier(store.schema,'registration_pages')),(order['flow_id'],)).fetchone()
 fields=(row[0] if row else {}).get('fields',[]);contacts=order['data']['contacts'];recipient=next((contacts.get(f['id'],'') for f in fields if f['type']=='email' and contacts.get(f['id'])),None)
 state='queued' if recipient and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',recipient) else 'blocked'
 c.execute(sql.SQL('INSERT INTO {}(order_id,recipient,status) VALUES(%s,%s,%s) ON CONFLICT(order_id) DO NOTHING').format(sql.Identifier(store.schema,'confirmation_delivery')),(order['id'],recipient or '',state))

def readiness(settings):
 config=settings.read();errors=settings.issues(config,'email')
 if config['email']['provider']=='smtp':errors.append('Confirmation delivery supports Bird or SendGrid; SMTP remains available for password recovery only.')
 if not config['public_url'].startswith('https://'):errors.append('Add the public HTTPS app origin for confirmation links.')
 if os.environ.get('REGFIRE_CONFIRMATION_EMAIL_LIVE')!='1':errors.append('Live confirmation email is disabled on this server.')
 if os.environ.get('REGFIRE_COMMUNICATIONS_LIVE')!='1':errors.append('Live communications delivery is disabled on this server.')
 return errors

def dispatch(store,settings,order_id,client=None,*,upload_root=None):
 """Called only by an explicitly authorized operator/worker. No UI or startup sends."""
 problems=readiness(settings)
 if problems:raise DeliveryError(' '.join(problems))
 table=sql.Identifier(store.schema,'confirmation_delivery')
 with store.connect() as c:
  row=c.execute(sql.SQL('SELECT recipient,status FROM {} WHERE order_id=%s FOR UPDATE').format(table),(order_id,)).fetchone()
  if not row or row[1]!='queued':raise DeliveryError('This confirmation is not queued. Reconcile uncertain submissions before retrying.')
  order=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(sql.Identifier(store.schema,'registration_orders')),(order_id,)).fetchone()
  if not order or order[0]['status'] not in ('paid','confirmed_free') or order[0].get('mode')=='sandbox':raise DeliveryError('A completed live registration is required.')
  order=order[0];recipient=row[0]
  # Finish local rendering before claiming a provider submission. Bad/missing assets
  # leave the queue retryable; no mail has been attempted at this point.
  from pathlib import Path
  from confirmation import document
  from confirmation_email import prepare
  cfg=settings.read()
  link=cfg['public_url']+'/confirmation#event='+order['flow_id']+'&order='+order['id']
  presentation=prepare(document(store,order['flow_id'],order),store,upload_root or Path(__file__).parent/'uploads',link)
  c.execute(sql.SQL("UPDATE {} SET status='submitting',updated=now() WHERE order_id=%s").format(table),(order_id,))
 # Commit the claim before contacting the provider. A crash/timeout remains uncertain, never auto-retried.
 quote=order['quote'];scale=1 if quote['currency']=='JPY' else 100;amount=quote['grand_total_minor']/scale if order['status']=='paid' else 0
 link=cfg['public_url']+'/confirmation#event='+order['flow_id']+'&order='+order['id']
 body='Your registration for '+quote['event_name']+' is confirmed.\n\nConfirmation: '+order['id']+'\n'+('Amount paid: '+quote['currency']+' '+format(amount,'.2f') if order['status']=='paid' else 'Free registration. No payment required.')+'\n\nView your confirmation, download your receipt and access available wallet passes:\n'+link+'\n\nSign in to the account used for registration.\n'
 try:
  result=adapter_for('email',cfg['email'],client).submit(recipient,'Your registration confirmation - '+quote['event_name'],body,**presentation)
  if result.get('status')!='submitted':raise DeliveryError('Provider acceptance is unknown.')
 except Exception:
  with store.connect() as c:c.execute(sql.SQL("UPDATE {} SET status='unknown',updated=now() WHERE order_id=%s").format(table),(order_id,))
  raise DeliveryError('Email submission could not be confirmed. Check the provider before retrying.') from None
 with store.connect() as c:c.execute(sql.SQL("UPDATE {} SET status='submitted',provider_id=%s,updated=now() WHERE order_id=%s").format(table),(result.get('provider_id'),order_id))
 return dict(status='submitted',message='Accepted by provider; recipient delivery is not yet verified.')
