"""One payment over separate attendee orders; all pricing remains server-authoritative."""
import copy,uuid
from psycopg import sql
from psycopg.types.json import Jsonb

def aggregate(orders):
 quotes=[o['quote'] for o in orders]
 if len({q['currency'] for q in quotes})!=1:raise ValueError('All attendees must use the same currency.')
 result=copy.deepcopy(quotes[0]);result['lines']=[]
 for i,q in enumerate(quotes,1):
  result['lines'].extend(dict(l,name='Attendee '+str(i)+' · '+l['name']) for l in q['lines'])
 for key in ('subtotal_minor','discount_minor','tax_minor','grand_total_minor'):
  result[key]=None if any(q[key] is None for q in quotes) else sum(q[key] for q in quotes)
 result['tax_pending']=any(q['tax_pending'] for q in quotes)
 return result

def quote_members(store,c,flow,members,config,exclude=()):
 from checkout import quote_order
 if not isinstance(members,list) or not 1<=len(members)<=20:raise ValueError('Add between one and twenty attendees.')
 result=[]
 for member in members:
  if not isinstance(member,dict):raise ValueError('Check attendee details.')
  eligibility=store.membership(flow,'check-fields',dict(regtype_id=member.get('regtype_id'),subcategory_path=member.get('subcategory_path',[]),values=member.get('contacts',{})),connection=c)
  if not eligibility or not eligibility.get('can_continue') or eligibility.get('status')=='pending':raise ValueError('Confirm membership eligibility for every attendee.')
  q,clean,parent=quote_order(store,c,flow,member,config,exclude,extra_held=result)
  result.append(dict(quote=q,data=clean,parent_event_id=parent))
 return result

def save(store,c,flow,actor,data,config,preview=False):
 from checkout import table,public
 key=str(uuid.UUID(data.get('request_key','')))
 # Serialize group creation and inventory decisions on the same event lock used by individual orders.
 event=c.execute(sql.SQL('SELECT body FROM {} WHERE id=%s').format(store.table()),(flow,)).fetchone()
 if not event:raise ValueError('Flow not found.')
 c.execute(sql.SQL('SELECT id FROM {} WHERE id=%s FOR UPDATE').format(store.table()),(event[0].get('parent_event_id',flow),)).fetchone()
 old=c.execute(sql.SQL('SELECT body FROM {} WHERE flow_id=%s AND actor_id=%s AND request_key=%s FOR UPDATE').format(table(store,'registration_orders')),(flow,actor,key)).fetchone()
 if old and not old[0].get('group_order_ids'):raise ValueError('Use a new group checkout request.')
 oldids=old[0]['group_order_ids'] if old else []
 members=data.get('members');quoted=quote_members(store,c,flow,members,config,oldids)
 total=aggregate(quoted)
 if preview:return dict(quote=total,attendees=[x['quote'] for x in quoted])
 if total['tax_pending']:raise ValueError('The organizer must configure tax before checkout.')
 # An existing pending group's attendee identities are immutable; edits use a new request key.
 if old:
  from checkout import get_order
  existing=[get_order(c,store,i,actor) for i in oldids]
  if len(existing)!=len(quoted) or any(a['data']!=b['data'] for a,b in zip(existing,quoted)):raise ValueError('This group was already saved. Start a new group checkout for changes.')
  return public(old[0])
 ids=[str(uuid.uuid4()) for _ in quoted];root=ids[0];orders=[]
 for i,(entry,member) in enumerate(zip(quoted,members)):
  if i and member.get('enrollment_token'):raise ValueError('Colleague registrations cannot create or take over attendee accounts.')
  o=entry|dict(id=ids[i],flow_id=flow,actor_id=actor,status='pending',group_parent_id=root)
  if i==0:o.update(group_order_ids=ids,payment_quote=total)
  request_key=key if i==0 else str(uuid.uuid5(uuid.UUID(key),str(i)))
  c.execute(sql.SQL('INSERT INTO {}(id,flow_id,actor_id,request_key,body,status) VALUES(%s,%s,%s,%s,%s,%s)').format(table(store,'registration_orders')),(o['id'],flow,actor,request_key,Jsonb(o),o['status']))
  if i==0:
   from attendee_accounts import bind
   bind(c,store,o,member.get('enrollment_token'))
  orders.append(o)
 return public(orders[0])

def revalidate(store,c,root,config):
 from checkout import get_order
 members=[get_order(c,store,i,root['actor_id']) for i in root['group_order_ids']]
 quoted=quote_members(store,c,root['flow_id'],[o['data'] for o in members],config,root['group_order_ids'])
 if any(a['quote']!=b['quote'] for a,b in zip(members,quoted)) or aggregate(quoted)!=root['payment_quote']:raise ValueError('Group prices or selections changed. Start a new group review before paying.')
 return root['payment_quote'],root['parent_event_id']

def propagate(c,store,root):
 from checkout import get_order,save_order
 for ident in root.get('group_order_ids',[])[1:]:
  child=get_order(c,store,ident,root['actor_id']);child['status']=root['status']
  for key in ('mode','connection_id','provider'):
   if key in root:child[key]=root[key]
  save_order(c,store,child)
