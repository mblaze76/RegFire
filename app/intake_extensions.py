"""Human-readable intake tables for per-flow registration configuration."""
import copy,uuid
from decimal import Decimal,InvalidOperation

HEADERS={
 'Flows':['Name','Kind'],
 'Flow settings':['Flow','Registration title','Registration intro','Demographics title','Demographics intro'],
 'Dated prices':['Category','Rate name','Price','Starts','Ends','Flow'],
 'Category settings':['Category','Default price enabled','Show on welcome','Membership lookup','Flow'],
 'Variants':['Item','Size or variant','Inventory','Flow'],
 'Attendee fields':['Field key','Label','Type','Required','Choices','Visible categories','SMS consent','Membership field','Flow'],
 'Demographics':['Question','Type','Required','Choices','Visible categories','Help','Flow'],
 'Branching':['Question','Match all or any','Earlier question','Operator','Answer','Flow'],
 'Subcategories':['Category','Parent path','Name','Membership lookup','Flow'],
 'Settings':['Section','Setting','Value','Flow'],
 'Session details':['Session','Credits','Status','Cancellation note','Flow'],
 'Promo codes':['Code','Type','Amount','Enabled','Allotment','Flow'],
 'Speakers':['Key','First name','Last name','Role','Organization','Bio','Flow'],
 'Session speakers':['Session','Speaker key','Flow'],
 'Welcome buttons':['Label','Destination flow'],
}
SCOPED=('Categories','Sessions','Additional options',*tuple(k for k in HEADERS if HEADERS[k][-1]=='Flow'))

def flows(tabs,normalize):
 definitions=tabs.get('Flows',[]) or [(2,['Attendee','attendee'])];seen=set();result=[]
 if len(definitions)>20:raise ValueError('Use at most 20 registration flows.')
 for row,values in definitions:
  name,kind=values
  if not name or len(name)>100 or name.casefold() in seen:raise ValueError('Flows: use distinct names of 1–100 characters.')
  if kind not in ('attendee','exhibitor','media','custom'):raise ValueError('Flows: choose attendee, exhibitor, media or custom.')
  seen.add(name.casefold());result.append(dict(name=name,kind=kind))
 for tab in SCOPED:
  for row,values in tabs.get(tab,[]):
   if values[-1] and values[-1].casefold() not in seen:raise ValueError(f'{tab} row {row}: unknown flow {values[-1]}.')
 for row,v in tabs.get('Flow settings',[]):
  if v[0].casefold() not in seen:raise ValueError(f'Flow settings row {row}: unknown flow.')
 for spec in result:
  selected=copy.deepcopy(tabs)
  for tab in SCOPED:selected[tab]=[(n,v[:-1]) for n,v in tabs.get(tab,[]) if not v[-1] or v[-1].casefold()==spec['name'].casefold()]
  data=normalize(selected,_single=True)
  extend(data,selected,spec['name'])
  spec['configuration']=data
 for section in ('welcome','footer'):
  if any(f['configuration'][section]!=result[0]['configuration'][section] for f in result):raise ValueError(section.capitalize()+': shared event settings must be identical across flows. Leave Flow blank for shared settings.')
 buttons=[]
 for _,v in tabs.get('Welcome buttons',[]):
  if not v[0] or len(v[0])>100 or v[1].casefold() not in seen:raise ValueError('Welcome buttons: use a label up to 100 characters and an existing flow name.')
  buttons.append(dict(label=v[0],flow_name=v[1].casefold()))
 if len(buttons)>100:raise ValueError('Use at most 100 welcome buttons.')
 primary=copy.deepcopy(result[0]['configuration']);primary['flows']=result;primary['welcome_buttons']=buttons
 return primary

def extend(data,tabs,flow_name):
 from registration import validate_page,CURRENCIES
 from demographics import validate as validate_demo
 from extra_options import validate as validate_extras
 reg=data['registration'];categories={x['name']:x for x in reg['regtypes']};items={x['name']:x for x in data['extras']['items']}
 ident=lambda key:str(uuid.uuid5(uuid.NAMESPACE_URL,'regfire-intake:'+key))
 def lookup(mapping,key,tab):
  if key not in mapping:raise ValueError(tab+': unknown reference '+key)
  return mapping[key]
 def flag(v,blank=False):
  if v.lower() not in ('yes','no',''):raise ValueError('Use Yes or No.')
  return v.lower()=='yes' if v else blank
 def lines(v):return [x.strip() for x in v.splitlines() if x.strip()]
 def visible(v):return [lookup(categories,x,'Visible categories')['id'] for x in lines(v)] if v else None
 def money(v):
  try:
   n=Decimal(v);m=n*10**CURRENCIES[reg['currency']]
   if not n.is_finite() or m!=m.to_integral_value() or not 0<=m<=99999999:raise ValueError()
   return int(m)
  except (InvalidOperation,ValueError):raise ValueError('Dated prices: enter a valid price in the event currency.') from None
 for _,v in tabs.get('Dated prices',[]):
  c=lookup(categories,v[0],'Dated prices');c.setdefault('rates',[]).append(dict(id=ident('rate:'+v[0]+':'+v[1]),name=v[1],price_minor=money(v[2]),start=v[3],end=v[4]))
 for _,v in tabs.get('Category settings',[]):
  c=lookup(categories,v[0],'Category settings');c.update(use_default=flag(v[1],True),show_on_welcome=flag(v[2],True),use_membership_lookup=flag(v[3]) if v[3] else None)
 for _,v in tabs.get('Variants',[]):
  item=lookup(items,v[0],'Variants')
  if v[2] and (not v[2].isdigit() or int(v[2])>1000000):raise ValueError('Variants: inventory must be blank or a whole number up to 1,000,000.')
  item.setdefault('variants',[]).append(dict(id=ident('variant:'+v[0]+':'+v[1]),label=v[1],inventory=int(v[2]) if v[2] else None))
 for _,v in tabs.get('Subcategories',[]):
  node=lookup(categories,v[0],'Subcategories')
  for name in v[1].split(' / ') if v[1] else []:node=lookup({x['name']:x for x in node.get('subcategories',[])},name,'Subcategory parent path')
  node.setdefault('subcategories',[]).append(dict(id=ident('subcategory:'+v[0]+':'+v[1]+':'+v[2]),name=v[2],use_membership_lookup=flag(v[3]) if v[3] else None,subcategories=[]))
 fields={x['id']:x for x in reg['fields']};field_seen=set()
 for _,v in tabs.get('Attendee fields',[]):
  if v[0] in field_seen:raise ValueError('Attendee fields: duplicate field key.')
  field_seen.add(v[0]);fields[v[0]]=dict(id=v[0],label=v[1],type=v[2],required=flag(v[3]),options=lines(v[4]),visible_to=visible(v[5]),sms_consent=flag(v[6]),membership_lookup=v[7] or '')
 reg['fields']=list(fields.values())
 questions=[];qmap={}
 for _,v in tabs.get('Demographics',[]):
  if v[0] in qmap:raise ValueError('Demographics: duplicate question label.')
  q=dict(id=ident('question:'+v[0]),label=v[0],type=v[1],required=flag(v[2]),options=[dict(id=ident('choice:'+v[0]+':'+x),label=x) for x in lines(v[3])],visible_to=visible(v[4]),help=v[5],conditions=dict(mode='all',rules=[]));questions.append(q);qmap[v[0]]=q
 modes={}
 for _,v in tabs.get('Branching',[]):
  q=lookup(qmap,v[0],'Branching');parent=lookup(qmap,v[2],'Branching');mode=v[1] or 'all'
  if v[0] in modes and modes[v[0]]!=mode:raise ValueError('Branching: use one match mode for each question.')
  modes[v[0]]=mode;value=v[4]
  if parent['type'] in ('radio','select','multiselect') and v[3]!='is_answered':value=lookup({x['label']:x for x in parent['options']},value,'Branching answer')['id']
  if parent['type']=='boolean' and v[3]!='is_answered':value=flag(value)
  q['conditions']['mode']=mode;q['conditions']['rules'].append(dict(question_id=parent['id'],operator=v[3],value=value))
 demo=dict(title='Demographics',intro='',questions=questions)
 matched=False
 for _,v in tabs.get('Flow settings',[]):
  if v[0].casefold()!=flow_name.casefold():continue
  if matched:raise ValueError('Flow settings: duplicate flow.')
  matched=True
  if v[1]:reg['title']=v[1]
  reg['intro']=v[2]
  if v[3]:demo['title']=v[3]
  demo['intro']=v[4]
 for _,v in tabs.get('Promo codes',[]):
  try:amount=float(v[2] or '0');allotment=int(v[4]) if v[4] else None
  except ValueError:raise ValueError('Promo codes: enter numeric amounts and whole-number allotments.') from None
  reg.setdefault('promo_codes',[]).append(dict(code=v[0],type=v[1],amount=amount,enabled=flag(v[3],True),allotment=allotment))
 session_map={x['title']:x for x in data['sessions']['sessions']}
 for _,v in tabs.get('Session details',[]):
  session=lookup(session_map,v[0],'Session details')
  try:credits=float(v[1]) if v[1] else None
  except ValueError:raise ValueError('Session details: credits must be numeric.') from None
  session.update(credits=credits,status=v[2] or 'active',cancellation_note=v[3])
 speakers={}
 for _,v in tabs.get('Speakers',[]):
  if not v[0] or v[0] in speakers:raise ValueError('Speakers: use distinct nonempty keys.')
  speakers[v[0]]=dict(id=ident('speaker:'+v[0]),first_name=v[1],last_name=v[2],role=v[3],organization=v[4],bio=v[5])
 data['sessions']['speakers']=list(speakers.values())
 for _,v in tabs.get('Session speakers',[]):lookup(session_map,v[0],'Session speakers').setdefault('speaker_ids',[]).append(lookup(speakers,v[1],'Session speakers')['id'])
 from event_footer import normalize as footer
 from payment_preferences import DEFAULT,validate as payment
 from membership import starter as member,validate as membership
 from welcome import validate as welcome
 from confirmation import validate as confirmation
 from sessions import validate as sessions
 data['demographics']=demo;data['footer']=footer({});data['payment']=copy.deepcopy(DEFAULT);data['membership']=member()
 data['intake_settings']=[];seen=set()
 allowed={'registration','demographics','welcome','footer','confirmation','payment','membership','sessions'}
 for _,v in tabs.get('Settings',[]):
  section,path,raw=v;key=(section,path)
  if key in seen:raise ValueError('Settings: duplicate setting '+section+'.'+path)
  seen.add(key)
  if section not in allowed:raise ValueError('Settings: choose a documented section.')
  parts=path.split('.')
  if section=='membership' and path=='source':raise ValueError('Membership source is connected through secure setup.')
  if any(x in ('id','event_id','status','revision','updated','created','currency','api','asset_event_id','buttons','title_font','about_font','details_font','font') or x.endswith('_font') or 'asset' in x or 'secret' in x or 'password' in x or 'credential' in x for x in parts):raise ValueError('Settings: this setting requires its owning setup control, artwork or secure provider connection: '+path)
  target=data[section]
  if section=='payment' and parts[0]=='tax':target.setdefault('tax',dict(rate_bps=0,jurisdiction='',source='',confirmed=False))
  for part in parts[:-1]:
   if part not in target or not isinstance(target[part],dict):raise ValueError('Settings: unknown setting '+path)
   target=target[part]
  name=parts[-1]
  if name not in target:raise ValueError('Settings: unknown setting '+path)
  existing=target[name]
  if isinstance(existing,dict) or isinstance(existing,list) and any(isinstance(x,dict) for x in existing):raise ValueError('Settings: use the dedicated table for record lists.')
  if name in ('fields','regtypes','questions','sessions','speakers','sponsors','promo_codes'):raise ValueError('Settings: use the dedicated table or artwork upload for '+name)
  if isinstance(existing,list):value=lines(raw)
  elif type(existing) is bool:value=flag(raw)
  elif type(existing) is int:
   try:value=int(raw)
   except ValueError:raise ValueError('Settings: enter a whole number for '+path) from None
  elif type(existing) is float:
   try:value=float(raw)
   except ValueError:raise ValueError('Settings: enter a number for '+path) from None
  else:value=raw or None if existing is None else raw
  if section=='membership' and name=='regtype_ids':value=visible(raw) or []
  target[name]=value;data['intake_settings'].append(dict(section=section,setting=path,value=raw))
 data['registration']=validate_page(reg,data['event']['timezone']);data['demographics']=validate_demo(demo,data['registration']['regtypes']);data['extras']=validate_extras(data['extras'])
 data['sessions']=sessions(data['sessions'],data['event']);data['welcome']=welcome(data['welcome']);data['footer']=footer(data['footer']);data['confirmation']=confirmation(data['confirmation']);data['payment']=payment(data['payment']);data['membership']=membership(data['membership'],data['registration']['regtypes'])
