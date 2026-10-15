import uuid,json,unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from psycopg import sql
from psycopg.types.json import Jsonb
import psycopg
import test_checkout as tc
from confirmation_numbers import number

class ConfirmationNumbers(tc.CheckoutStorage):
 def test_number_stable_lookup_and_old_qr(self):
  flow,_,data=self.setup_order(0)
  order=self.request('/api/events/'+flow+'/checkout/save',data,'POST')
  self.request('/api/checkout/'+order['id']+'/start',{},'POST')
  path='/api/checkout/'+order['id']+'/confirmation'
  doc=self.request(path);n=doc['confirmation_number']
  self.assertRegex(n,r'^[1-9][0-9]{7}$')
  self.assertEqual(json.loads(doc['qr_payload'])['confirmation_id'],order['id'])
  self.store.initialize()
  self.assertEqual(self.request(path)['confirmation_number'],n)
  for ref in (n,order['id']):
   found=self.request('/api/events/'+flow+'/confirmation/lookup/'+ref)
   self.assertEqual(found['confirmation_number'],n)
  other,_,_=self.setup_order(0)
  with self.assertRaises(HTTPError) as e:self.request('/api/events/'+other+'/confirmation/lookup/'+n)
  self.assertEqual(e.exception.code,404)
  with self.assertRaises(HTTPError) as e:self.request('/api/events/'+flow+'/confirmation/lookup/'+n,headers={'Cookie':''})
  self.assertEqual(e.exception.code,401)
  from confirmation_email import render
  # Renderer keeps the public number bold and QR identifiers independent.
  html=render(doc)
  self.assertIn('<strong>'+n+'</strong>',html)

 def test_concurrent_assignment_and_immutable_database_value(self):
  flow,_,_=self.setup_order(0)
  actor=self.access.session(self.raw_session)['id']
  def insert(_):
   ident=str(uuid.uuid4())
   with self.store.connect() as c:
    return c.execute(sql.SQL('INSERT INTO {}(id,flow_id,actor_id,request_key,body) VALUES(%s,%s,%s,%s,%s) RETURNING confirmation_number').format(sql.Identifier(self.schema,'registration_orders')),(ident,flow,actor,str(uuid.uuid4()),Jsonb({}))).fetchone()[0]
  with ThreadPoolExecutor(max_workers=8) as pool:values=list(pool.map(insert,range(32)))
  self.assertEqual(len(set(values)),32)
  self.assertTrue(all(10000000<=v<=99999999 for v in values))
  with self.assertRaises(psycopg.Error):
   with self.store.connect() as c:c.execute(sql.SQL('UPDATE {} SET confirmation_number=confirmation_number+1').format(sql.Identifier(self.schema,'registration_orders')))

 def test_legacy_backfill_preserves_uuid_and_is_repeatable(self):
  flow,_,data=self.setup_order(0)
  order=self.request('/api/events/'+flow+'/checkout/save',data,'POST')
  self.request('/api/checkout/'+order['id']+'/start',{},'POST')
  with self.store.connect() as c:
   t=sql.Identifier(self.schema,'registration_orders')
   c.execute(sql.SQL('DROP TRIGGER preserve_confirmation_number ON {}').format(t))
   c.execute(sql.SQL('ALTER TABLE {} DROP COLUMN confirmation_number').format(t))
  self.store.initialize()
  first=number(self.store,order['id'])
  self.store.initialize()
  self.assertEqual(number(self.store,order['id']),first)
  doc=self.request('/api/checkout/'+order['id']+'/confirmation')
  self.assertEqual(doc['confirmation_id'],order['id'])
  self.assertEqual(doc['confirmation_number'],first)
