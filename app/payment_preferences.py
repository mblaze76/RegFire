"""Nonsensitive flow payment plans. These never authorize a provider or charge."""
import copy
from psycopg import sql
from psycopg.types.json import Jsonb
DEFAULT={'processor':'undecided','methods':['card'],'cards':['visa','mastercard','amex'],'revision':0}
PROCESSORS={'undecided','stripe','paypal','square','authorize_net','other'}
METHODS={'card','paypal','apple_pay','google_pay','bank_transfer','invoice'}
CARDS={'visa','mastercard','amex','discover'}
def validate(data):
 if not isinstance(data,dict) or set(data)-{'processor','methods','cards','revision','tax'}:raise ValueError('Save payment preferences only; do not enter credentials.')
 if data.get('processor') not in PROCESSORS:raise ValueError('Choose a processor preference.')
 out={'processor':data['processor']}
 for key,allowed in [('methods',METHODS),('cards',CARDS)]:
  value=data.get(key)
  if not isinstance(value,list) or (not value and (key=='methods' or 'card' in data.get('methods',[]))) or any(not isinstance(v,str) or v not in allowed for v in value) or len(set(value))!=len(value):raise ValueError('Choose valid '+key+'.')
  out[key]=value[:]
 if 'tax' in data:
  tax=data['tax']
  if tax is not None:
   if not isinstance(tax,dict) or set(tax)-{'rate_bps','jurisdiction','source','confirmed'}:raise ValueError('Enter a manual tax rate and its source.')
   rate=tax.get('rate_bps')
   if type(rate) is not int or not 0<=rate<=10000:raise ValueError('Tax must be 0 to 100 percent with at most two decimal places.')
   if tax.get('confirmed') is not True:raise ValueError('Confirm the rate before applying it to this flow.')
   for key in ('jurisdiction','source'):
    if not isinstance(tax.get(key),str) or not 1<=len(tax[key].strip())<=200:raise ValueError('Enter the tax jurisdiction and source, up to 200 characters each.')
   tax=dict(rate_bps=rate,jurisdiction=tax['jurisdiction'].strip(),source=tax['source'].strip(),confirmed=True)
  out['tax']=tax
 return out

def operation(store,flow,data=None):
 with store.connect() as c:
  found=c.execute(sql.SQL('SELECT id FROM {} WHERE id=%s AND NOT archived FOR UPDATE').format(sql.Identifier(store.schema,'registration_flows')),(flow,)).fetchone()
  if not found:raise ValueError('Registration flow not found.')
  table=sql.Identifier(store.schema,'payment_preferences')
  row=c.execute(sql.SQL('SELECT body,revision FROM {} WHERE flow_id=%s').format(table),(flow,)).fetchone()
  result=copy.deepcopy(DEFAULT) if not row else row[0]|{'revision':row[1]}
  if data is not None:
   if type(data.get('revision')) is not int or data['revision']!=result['revision']:raise ValueError('Payment preferences changed in another tab. Reload before saving; your edits are still here.')
   updated=validate(data)
   if 'tax' not in updated and 'tax' in result:updated['tax']=result['tax']
   result=updated|{'revision':result['revision']+1}
   c.execute(sql.SQL('INSERT INTO {}(flow_id,body,revision) VALUES(%s,%s,%s) ON CONFLICT(flow_id) DO UPDATE SET body=excluded.body,revision=excluded.revision').format(table),(flow,Jsonb({k:v for k,v in result.items() if k!='revision'}),result['revision']))
  return result
