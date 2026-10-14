"""Ownership-checked contact corrections; financial and inventory selections stay locked."""
import copy,hashlib,json
from psycopg import sql
from psycopg.types.json import Jsonb
from access import AccessError
from attendee_accounts import table

def operation(store,account,ident,changes=None):
 with store.connect() as c:
  row=c.execute(sql.SQL("SELECT o.body FROM {} o JOIN {} a ON a.order_id=o.id WHERE a.account_id=%s AND o.id=%s AND o.status IN ('paid','confirmed_free') FOR UPDATE OF o").format(table(store,'registration_orders'),table(store,'attendee_order_access')),(account,ident)).fetchone()
  if not row:raise AccessError('Registration unavailable for this account.',403)
  order=copy.deepcopy(row[0]);version=hashlib.sha256(json.dumps(order,sort_keys=True).encode()).hexdigest()
  page=store.registration_page(order['flow_id'])
  fields=[f for f in page['fields'] if f['type'] in ('text','tel') and not f.get('readonly') and (f.get('visible_to') is None or order['data']['regtype_id'] in f['visible_to'])]
  permitted={f['id']:f for f in fields};contacts=order['data']['contacts']
  if changes is not None:
   if set(changes)!={'id','version','contacts'} or changes['version']!=version:raise ValueError('Registration changed. Reload before saving your corrections.')
   values=changes['contacts']
   if not isinstance(values,dict) or set(values)-set(permitted):raise ValueError('Only the displayed contact fields can be changed here.')
   for key,value in values.items():
    if not isinstance(value,str) or len(value)>500 or (permitted[key].get('required') and not value.strip()):raise ValueError('Check the required contact fields and length.')
    if permitted[key]['type']=='tel' and contacts.get(key)!=value.strip():
     order['data'].setdefault('smsConsents',{})[key]=False
     for detail in order['quote']['details']:
      if detail['label']==permitted[key]['label']+' SMS consent':detail['value']=False
    contacts[key]=value.strip()
   # Quote details carry stable field IDs; update only matching contact display data.
   for detail in order['quote']['details']:
    key=detail.get('id')
    if not key:
     matches=[f['id'] for f in fields if f['label']==detail['label']]
     key=matches[0] if len(matches)==1 else None
    if key in values:detail['value']=contacts[key]
   c.execute(sql.SQL('UPDATE {} SET body=%s,updated=now() WHERE id=%s').format(table(store,'registration_orders')),(Jsonb(order),ident))
   version=hashlib.sha256(json.dumps(order,sort_keys=True).encode()).hexdigest()
  return dict(id=ident,version=version,fields=[{k:f[k] for k in ('id','label','type','required') if k in f} for f in fields],contacts={k:contacts.get(k,'') for k in permitted},message='You can correct contact details here. Email, registration type, sessions and additional options require organizer assistance so capacity, payment differences and refunds can be reviewed. No payment or email is triggered by saving.')
