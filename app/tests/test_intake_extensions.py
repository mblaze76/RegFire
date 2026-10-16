import copy,unittest
import client_intake as ci
from test_client_intake import workbook
import test_checkout as tc
from psycopg import sql

def rich_tabs():
 t=ci.workbook(workbook(rich=True));t['Flows']=[(2,['Guests','attendee']),(3,['Press','media'])]
 t['Additional options'][0][1][4]=''
 t['Variants']=[(2,['Tote','Small','12','Guests']),(3,['Tote','Large','7','Guests'])]
 t['Dated prices']=[(2,['Attendee','Early','15.00','2027-01-01T00:00','2027-04-01T00:00','Guests'])]
 t['Category settings']=[(2,['Attendee','Yes','Yes','No','Guests'])]
 t['Attendee fields']=[(2,['company','Company','text','Yes','','','No','',''])]
 t['Demographics']=[(2,['Interest','select','Yes','Technology\nOperations','','Area of interest','Guests']),(3,['Details','text','No','','','','Guests'])]
 t['Branching']=[(2,['Details','all','Interest','equals','Technology','Guests'])]
 t['Subcategories']=[(2,['Attendee','','Partner','No','Guests']),(3,['Attendee','Partner','Gold','','Guests'])]
 t['Settings']=[(2,['footer','message','Contact the event team','']),(3,['confirmation','qr_position','top','']),(4,['payment','tax.rate_bps','725','Guests']),(5,['payment','tax.jurisdiction','Synthetic jurisdiction','Guests']),(6,['payment','tax.source','Synthetic test source','Guests']),(7,['payment','tax.confirmed','Yes','Guests'])]
 t['Promo codes']=[(2,['TEST','percent','10','Yes','20','Guests'])]
 t['Speakers']=[(2,['jordan','Jordan','Sample','Host','Example','Synthetic biography','Guests'])]
 t['Session speakers']=[(2,['Opening keynote','jordan','Guests'])]
 t['Session details']=[(2,['Opening keynote','1.5','active','','Guests'])]
 t['Welcome buttons']=[(2,['Register as a guest','Guests']),(3,['Press registration','Press'])]
 t['Flow settings']=[(2,['Guests','Guest registration','Welcome guests','About you','Choose your interests'])]
 return t
class ExtensionParser(unittest.TestCase):
 def test_flow_scoped_fields_variants_rates_branching(self):
  d=ci.normalize(rich_tabs());a,b=[x['configuration'] for x in d['flows']]
  self.assertEqual(a['extras']['items'][0]['variants'][1]['inventory'],7);self.assertFalse(b['extras']['items'][0]['variants'])
  self.assertEqual(a['registration']['regtypes'][0]['rates'][0]['price_minor'],1500);self.assertFalse(b['registration']['regtypes'][0]['rates'])
  self.assertEqual(a['demographics']['questions'][1]['conditions']['rules'][0]['value'],a['demographics']['questions'][0]['options'][0]['id'])
  self.assertEqual(a['payment']['tax']['rate_bps'],725);self.assertEqual(a['footer']['message'],'Contact the event team');self.assertEqual(a['confirmation']['qr_position'],'top');self.assertEqual(a['sessions']['sessions'][0]['credits'],1.5);self.assertEqual(a['registration']['promo_codes'][0]['amount'],10);self.assertEqual(len(a['sessions']['sessions'][0]['speaker_ids']),1)
  self.assertEqual(a['registration']['title'],'Guest registration');self.assertFalse(b['demographics']['questions'])
  self.assertEqual(a['registration']['regtypes'][0]['subcategories'][0]['subcategories'][0]['name'],'Gold')
 def test_unknown_flow_reference_and_variant_stock_conflict(self):
  t=rich_tabs();t['Variants'][0][1][-1]='Missing'
  with self.assertRaises(ValueError):ci.normalize(t)
  t=rich_tabs();t['Additional options'][0][1][4]='20'
  with self.assertRaises(ValueError):ci.normalize(t)
 def test_settings_secrets_invalid_field_and_shared_conflict_rejected(self):
  for section,key,value,flow in [('membership','api.credential_env','SECRET',''),('payment','secret','SECRET',''),('confirmation','unknown','x',''),('registration','appearance.intro_font','georgia',''),('footer','message','conflict','Press')]:
   t=rich_tabs();t['Settings'].append((10,[section,key,value,flow]))
   with self.assertRaises(ValueError):ci.normalize(t)
 def test_overlap_duplicate_flow_branching_forward_reference(self):
  for mutation in [lambda t:t['Flows'].append((4,['guests','custom'])),lambda t:t['Dated prices'].append((3,['Attendee','Overlap','20','2027-03-01T00:00','2027-04-15T00:00','Guests'])),lambda t:t['Branching'].__setitem__(0,(2,['Interest','all','Details','equals','x','Guests']))]:
   t=rich_tabs();mutation(t)
   with self.assertRaises(ValueError):ci.normalize(t)
class ExtensionStorage(unittest.TestCase):
 setUp=tc.CheckoutStorage.setUp;tearDown=tc.CheckoutStorage.tearDown;start=tc.CheckoutStorage.start;stop=tc.CheckoutStorage.stop;request=tc.CheckoutStorage.request;auth_headers=tc.CheckoutStorage.auth_headers
 def test_multiple_flow_atomic_apply_persistence(self):
  import uuid
  from psycopg.types.json import Jsonb
  who=self.request('/api/auth/me')['user']['id'];token=str(uuid.uuid4());data=ci.normalize(rich_tabs())
  with self.store.connect() as c:c.execute(sql.SQL('INSERT INTO {}(id,user_id,body) VALUES(%s,%s,%s)').format(ci.table(self.store,'client_intake_previews')),(token,who,Jsonb(data)))
  result=ci.apply(self.store,who,token);flows=self.store.flows(result['event_id']);self.assertEqual([f['name'] for f in flows],['Guests','Press'])
  self.assertEqual(len(self.store.demographics_page(flows[0]['id'])['questions']),2);self.assertEqual(len(self.store.demographics_page(flows[1]['id'])['questions']),0)
  self.assertEqual(self.request('/api/events/'+flows[0]['id']+'/extra-options')['items'][0]['variants'][0]['inventory'],12)
  buttons=self.store.welcome_page(result['event_id'])['buttons'];self.assertEqual(buttons[1]['flow_id'],flows[1]['id'])
  self.assertTrue(ci.apply(self.store,who,token)['already_applied'])
  for f in flows:self.assertFalse(self.request('/api/events/'+f['id']+'/publication')['published'])
