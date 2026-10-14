"""Nonsensitive flow payment plans. These never authorize a provider or charge."""
import copy
from psycopg import sql
from psycopg.types.json import Jsonb
DEFAULT={'processor':'undecided','methods':['card'],'cards':['visa','mastercard','amex'],'revision':0}
PROCESSORS={'undecided','stripe','paypal','square','authorize_net','other'}
METHODS={'card','paypal','apple_pay','google_pay','bank_transfer','invoice'}
CARDS={'visa','mastercard','amex','discover'}
def validate(data):
 if not isinstance(data,dict) or set(data)-{'processor','methods','cards','revision'}:raise ValueError('Save payment preferences only; do not enter credentials.')
 if data.get('processor') not in PROCESSORS:raise ValueError('Choose a processor preference.')
 out={'processor':data['processor']}
 for key,allowed in [('methods',METHODS),('cards',CARDS)]:
  value=data.get(key)
  if not isinstance(value,list) or (not value and (key=='methods' or 'card' in data.get('methods',[]))) or any(not isinstance(v,str) or v not in allowed for v in value) or len(set(value))!=len(value):raise ValueError('Choose valid '+key+'.')
  out[key]=value[:]
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
   result=validate(data)|{'revision':result['revision']+1}
   c.execute(sql.SQL('INSERT INTO {}(flow_id,body,revision) VALUES(%s,%s,%s) ON CONFLICT(flow_id) DO UPDATE SET body=excluded.body,revision=excluded.revision').format(table),(flow,Jsonb({k:v for k,v in result.items() if k!='revision'}),result['revision']))
  return result
