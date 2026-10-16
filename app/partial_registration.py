"""Account-bound incomplete drafts. No background or automatic reminder sends."""
import copy,hashlib,hmac,json,os,re,secrets,uuid
import psycopg
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit,parse_qs
from psycopg import sql
from psycopg.types.json import Jsonb
from access import AccessError
from communications_providers import DeliveryError
from publication_snapshot import load,digest

def table(store,name='partial_registrations'):return sql.Identifier(store.schema,name)
def cutoff(event):
 try:
  raw=event['end'];zone=ZoneInfo(event['timezone']);end=datetime.fromisoformat(raw)
  if end.tzinfo is not None:raise ValueError()
  local=end.replace(tzinfo=zone)
  if local.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)!=end:raise ValueError()
  return (local+timedelta(days=30)).astimezone(timezone.utc)
 except (ValueError,KeyError,TypeError,OverflowError):raise ValueError('An event end date and timezone are required to retain incomplete registrations.') from None

def sanitize(data,snapshot,*,member=False):
 if not isinstance(data,dict):raise ValueError('Send registration details.')
 # Explicit allowlist: no passwords, enrollment tokens, card data or provider fields.
 keys=('regtype_id','subcategory_path','contacts','answers','sessions','extras','promo_code','smsConsents')
 result={k:copy.deepcopy(data[k]) for k in keys if k in data}
 page=snapshot['registration_pages'];fields={f['id']:f for f in page['fields']};questions={q['id'] for q in snapshot['demographics_pages']['questions']}
 contacts=result.get('contacts',{})
 if not isinstance(contacts,dict):raise ValueError('Invalid attendee details.')
 result['contacts']={k:v for k,v in contacts.items() if k in fields}
 answers=result.get('answers',{})
 if not isinstance(answers,dict):raise ValueError('Invalid demographic answers.')
 result['answers']={k:v for k,v in answers.items() if k in questions}
 for key in ('subcategory_path','sessions','extras'):
  if key in result and (not isinstance(result[key],list) or len(result[key])>500):raise ValueError('Invalid selections.')
 for key in ('regtype_id','promo_code'):
  if key in result and (not isinstance(result[key],str) or len(result[key])>100):raise ValueError('Invalid registration choice.')
 for key in ('subcategory_path','sessions'):
  if any(not isinstance(v,str) or len(v)>100 for v in result.get(key,[])):raise ValueError('Invalid selection IDs.')
 for key,value in list(result['contacts'].items()):
  if fields[key]['type']=='address':
   if not isinstance(value,dict):raise ValueError('Invalid address.')
   value={k:v for k,v in value.items() if k in ('line1','line2','city','region','postal','country')}
   if any(not isinstance(v,str) for v in value.values()):raise ValueError('Invalid address.')
   result['contacts'][key]=value
  elif not isinstance(value,(str,bool)) and value is not None:raise ValueError('Invalid attendee response.')
 for value in result['answers'].values():
  if isinstance(value,list):
   if any(not isinstance(v,str) for v in value):raise ValueError('Invalid demographic response.')
  elif not isinstance(value,(str,bool)) and value is not None:raise ValueError('Invalid demographic response.')
 if 'extras' in result:
  if any(not isinstance(v,dict) for v in result['extras']):raise ValueError('Invalid additional options.')
  result['extras']=[{k:v[k] for k in ('item_id','variant_id','quantity') if k in v} for v in result['extras']]
  for item in result['extras']:
   if not isinstance(item.get('item_id'),str) or (item.get('variant_id') is not None and not isinstance(item['variant_id'],str)) or type(item.get('quantity')) is not int or not 0<=item['quantity']<=1000000:raise ValueError('Invalid additional option.')
 if 'smsConsents' in result:
  if not isinstance(result['smsConsents'],dict):raise ValueError('Invalid consent details.')
  result['smsConsents']={k:v for k,v in result['smsConsents'].items() if k in fields and type(v) is bool}
 def bounded(v,depth=0):
  if depth>4:raise ValueError('Registration details are too complex.')
  if isinstance(v,dict):
   if len(v)>100 or any(not isinstance(k,str) or len(k)>100 for k in v):raise ValueError('Invalid details.')
   for x in v.values():bounded(x,depth+1)
  elif isinstance(v,list):
   if len(v)>500:raise ValueError('Too many selections.')
   for x in v:bounded(x,depth+1)
  elif isinstance(v,str):
   if len(v)>10000:raise ValueError('A response is too long.')
  elif v is not None and type(v) not in (bool,int):raise ValueError('Invalid response.')
 bounded(result)
 if not member and data.get('group_members'):
  members=data['group_members'];index=data.get('group_index',0)
  if not isinstance(members,list) or not 1<=len(members)<=20 or type(index) is not int or not 0<=index<len(members):raise ValueError('Invalid registration group.')
  members=[sanitize(v,snapshot,member=True) for v in members];members[index]=copy.deepcopy(result)
  result['group_members']=members;result['group_index']=index
 if len(json.dumps(result).encode())>100000:raise ValueError('Registration draft is too large.')
 return result

def cleanup(store):
 """Lazy/worker cleanup removes incomplete records only, never completed orders."""
 with store.connect() as c:
  result=c.execute(sql.SQL("DELETE FROM {} d WHERE d.expires<=now() OR EXISTS(SELECT 1 FROM {} o WHERE o.flow_id=d.flow_id AND o.actor_id=d.account_id AND o.status IN ('paid','confirmed_free') AND o.updated>=d.created)").format(table(store),table(store,'registration_orders')))
  return result.rowcount

def save(store,flow,account,data):
 snapshot=load(store,flow)
 if not snapshot:raise ValueError('Publish this registration flow before saving incomplete registrations.')
 expires=cutoff(snapshot['parent'])
 if expires<=datetime.now(timezone.utc):raise ValueError('The incomplete-registration retention period has ended.')
 body=sanitize(data,snapshot);cleanup(store)
 with store.connect() as c:
  ident=str(uuid.uuid4())
  row=c.execute(sql.SQL('INSERT INTO {}(id,flow_id,account_id,body,publication_digest,expires) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(flow_id,account_id) DO UPDATE SET body=excluded.body,publication_digest=excluded.publication_digest,updated=now(),expires=excluded.expires RETURNING id').format(table(store)),(ident,flow,account,Jsonb(body),digest(snapshot),expires)).fetchone()
 return dict(id=str(row[0]),saved=True,expires=expires.isoformat())

def listing(store,flow,offset=0):
 cleanup(store)
 if type(offset) is not int or not 0<=offset<=100000:raise ValueError('Invalid draft page.')
 with store.connect() as c:
  rows=c.execute(sql.SQL('SELECT d.id,a.email,d.updated,d.expires,d.email_status FROM {} d JOIN {} a ON a.id=d.account_id WHERE d.flow_id=%s ORDER BY d.updated DESC,d.id LIMIT 100 OFFSET %s').format(table(store),table(store,'attendee_accounts')),(flow,offset)).fetchall()
 return [dict(id=str(r[0]),email=r[1],updated=r[2].isoformat(),expires=r[3].isoformat(),email_status=r[4]) for r in rows]

def summary(body,snapshot):
 if not snapshot:return []
 rows=[];members=body.get('group_members') or [body]
 for i,member in enumerate(members,1):
  prefix=('Attendee '+str(i)+' · ') if len(members)>1 else ''
  page=snapshot['registration_pages'];category=next((x['name'] for x in page['regtypes'] if x['id']==member.get('regtype_id')),'Not selected')
  rows.append(dict(label=prefix+'Registration type',value=category))
  for field in page['fields']:
   if field['id'] in member.get('contacts',{}):rows.append(dict(label=prefix+field['label'],value=member['contacts'][field['id']]))
  for question in snapshot['demographics_pages']['questions']:
   if question['id'] not in member.get('answers',{}):continue
   value=member['answers'][question['id']];options={o['id']:o['label'] for o in question.get('options',[])}
   value=[options.get(x,x) for x in value] if isinstance(value,list) else options.get(value,value) if isinstance(value,str) else value
   rows.append(dict(label=prefix+question['label'],value=value))
  sessions={x['id']:x['title'] for x in snapshot['event_sessions']['sessions']}
  rows.append(dict(label=prefix+'Sessions',value=[sessions.get(x,'Previously selected session — review required') for x in member.get('sessions',[])]))
  items={x['id']:x for x in snapshot['extra_options']['items']};extra=[]
  for x in member.get('extras',[]):
   item=items.get(x.get('item_id'),{});variant=next((v['label'] for v in item.get('variants',[]) if v['id']==x.get('variant_id')),'')
   extra.append(str(x.get('quantity',0))+' × '+item.get('name','Previously selected option — review required')+(' · '+variant if variant else ''))
  rows.append(dict(label=prefix+'Additional options',value=extra))
 return rows

def review(store,flow,ident):
 cleanup(store)
 with store.connect() as c:
  r=c.execute(sql.SQL('SELECT d.body,d.updated,d.email_status,a.email FROM {} d JOIN {} a ON a.id=d.account_id WHERE d.id=%s AND d.flow_id=%s AND d.expires>now()').format(table(store),table(store,'attendee_accounts')),(ident,flow)).fetchone()
 if not r:raise ValueError('Incomplete registration not found.')
 snapshot=load(store,flow)
 if not snapshot:raise ValueError('The registration site must be published before sending a reminder.')
 subject='Finish your registration for '+snapshot['parent']['name']
 text='You started registering for '+snapshot['parent']['name']+'. Sign in to the same attendee account to review and finish your registration. Prices and availability will be checked again.\n\n[Private resume link, valid for up to seven days]\n\nIf you no longer plan to attend, no action is needed. Your incomplete draft is deleted 30 days after the event ends.'
 return dict(summary=summary(r[0],snapshot),id=ident,recipient=r[3],subject=subject,body=text,status=r[2],review_digest=digest(dict(body=r[0],updated=r[1].isoformat(),recipient=r[3],publication=digest(snapshot))))

def send(store,settings,flow,ident,review_digest,client=None):
 from confirmation_delivery import readiness
 from communications_providers import adapter_for
 if os.environ.get('REGFIRE_PARTIAL_EMAIL_LIVE')!='1':raise DeliveryError('Partial-registration emails are disabled. No email was sent.')
 issues=readiness(settings)
 if issues:raise DeliveryError(' '.join(issues))
 preview=review(store,flow,ident)
 if not hmac.compare_digest(preview['review_digest'],str(review_digest)):raise ValueError('This draft changed. Review the reminder again.')
 cfg=settings.read();raw=secrets.token_urlsafe(32);hashed=hashlib.sha256(raw.encode()).hexdigest()
 with store.connect() as c:
  r=c.execute(sql.SQL('SELECT email_status,updated FROM {} WHERE id=%s AND flow_id=%s AND expires>now() FOR UPDATE').format(table(store)),(ident,flow)).fetchone()
  if not r or r[0]!='not_sent':raise ValueError('A reminder was already attempted. Reconcile its delivery before any resend.')
  # Recheck version under the same row lock used to claim this one send.
  latest=c.execute(sql.SQL('SELECT body,publication_digest FROM {} WHERE id=%s').format(table(store)),(ident,)).fetchone()
  check=digest(dict(body=latest[0],updated=r[1].isoformat(),recipient=preview['recipient'],publication=digest(load(store,flow))))
  if check!=preview['review_digest']:raise ValueError('This draft changed. Review the reminder again.')
  c.execute(sql.SQL("UPDATE {} SET email_status='submitting',token_hash=%s,token_expires=LEAST(expires,now()+interval '7 days') WHERE id=%s").format(table(store)),(hashed,ident))
 link=cfg['public_url'].rstrip('/')+'/register#event='+flow+'&mode=registration&resume='+raw
 text=preview['body'].replace('[Private resume link, valid for up to seven days]',link)
 try:
  result=adapter_for('email',cfg['email'],client).submit(preview['recipient'],preview['subject'],text)
  if result.get('status')!='submitted':raise DeliveryError('Unknown provider result.')
 except Exception:
  with store.connect() as c:c.execute(sql.SQL("UPDATE {} SET email_status='unknown' WHERE id=%s").format(table(store)),(ident,))
  raise DeliveryError('Submission is uncertain. Check the provider before attempting another reminder.') from None
 with store.connect() as c:c.execute(sql.SQL("UPDATE {} SET email_status='submitted',provider_id=%s WHERE id=%s").format(table(store)),(result.get('provider_id'),ident))
 return dict(status='submitted',message='Accepted by provider; inbox delivery is not verified.')

def resume(store,flow,account,token):
 cleanup(store)
 if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{40,100}',token):raise ValueError('Resume link is invalid or expired.')
 snapshot=load(store,flow)
 if not snapshot:raise ValueError('Registration is unavailable.')
 with store.connect() as c:
  r=c.execute(sql.SQL('SELECT id,body FROM {} WHERE flow_id=%s AND account_id=%s AND token_hash=%s AND token_expires>now() AND expires>now() FOR UPDATE').format(table(store)),(flow,account,hashlib.sha256(token.encode()).hexdigest())).fetchone()
  if not r:raise ValueError('Resume link is invalid, expired or belongs to another attendee account.')
  body=sanitize(r[1],snapshot)
  if body.get('group_members'):
   members=body['group_members'];body={**members[0],'group_members':members,'group_index':0,'colleague':False}
  # The link cannot silently recreate an enrollment or mark a registration paid.
  c.execute(sql.SQL('UPDATE {} SET token_hash=NULL,token_expires=NULL WHERE id=%s').format(table(store)),(r[0],))
 return dict(details=body,message='Draft restored. Review all answers and sign in with your attendee password before checkout. Prices and availability will be checked again.')

def handle(h):
 match=re.fullmatch(r'/api/events/([a-f0-9-]{36})/partial-registrations(?:/([a-f0-9-]{36})/(preview|send))?',urlsplit(h.path).path)
 if not match:return False
 try:
  flow,ident,action=match.groups()
  if getattr(h,'identity',{}).get('role')=='public-attendee':raise AccessError('Organizer access required.',403)
  if h.command=='GET':h.respond(200,review(h.server.store,flow,ident) if action=='preview' else dict(drafts=listing(h.server.store,flow,int(parse_qs(urlsplit(h.path).query).get('offset',['0'])[0]))) if not action else {'error':'Use POST.'})
  elif h.command=='POST' and action=='send':
   size=int(h.headers.get('Content-Length','0'))
   if not 0<size<2048:raise ValueError('Invalid send request.')
   data=json.loads(h.rfile.read(size))
   if data.get('confirmed') is not True:raise ValueError('Review and explicitly confirm this recipient before sending.')
   from communications import settings_for
   h.respond(200,send(h.server.store,settings_for(h.server),flow,ident,data.get('review_digest')))
  else:h.respond(405,{'error':'Method not allowed.'})
 except AccessError as e:h.respond(e.status,{'error':str(e)})
 except (ValueError,TypeError,DeliveryError) as e:h.respond(400,{'error':str(e)})
 except psycopg.Error:h.respond(503,{'error':'Incomplete registration storage is temporarily unavailable.'})
 return True
