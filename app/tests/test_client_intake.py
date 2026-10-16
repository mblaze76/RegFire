import unittest,io,zipfile,base64,uuid
from xml.sax.saxutils import escape
from urllib.error import HTTPError
import client_intake as ci
import test_checkout as tc

def workbook(formula=False,rich=False):
 tabs={name:[headers] for name,headers in ci.HEADERS.items()}
 tabs['Event'] += [[k,v,''] for k,v in dict(name='Synthetic Intake',start='2027-05-01T09:00',end='2027-05-01T17:00',timezone='America/Chicago',format='in_person',currency='USD').items()]
 tabs['Categories'] += [['Attendee','25.00']]
 if rich:tabs['Sessions'] += [['Opening keynote','2027-05-01','09:00','10:00','Main Hall','Technology','Jordan Sample','A synthetic session','5.00','100']]
 tabs['Additional options'] += [['Tote','Synthetic only','physical','10.00','20','Yes','Yes']]
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w') as z:
  z.writestr('xl/workbook.xml','<workbook xmlns="'+ci.NS['s']+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{escape(name)}" r:id="r{i}"/>' for i,name in enumerate(tabs))+'</sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<Relationships>'+''.join(f'<Relationship Id="r{i}" Target="worksheets/s{i}.xml"/>' for i in range(len(tabs)))+'</Relationships>')
  for i,(name,rows) in enumerate(tabs.items()):
   body=''
   for r,values in enumerate(rows,1):
    cells=''.join(f'<c r="{chr(65+c)}{r}" t="inlineStr"><is><t>{escape(value)}</t></is>'+('<f>1+1</f>' if formula and name=='Categories' and r==2 and c==1 else '')+'</c>' for c,value in enumerate(values))
    body+=f'<row r="{r}">{cells}</row>'
   z.writestr(f'xl/worksheets/s{i}.xml','<worksheet xmlns="'+ci.NS['s']+'"><sheetData>'+body+'</sheetData></worksheet>')
 return out.getvalue()
class IntakeParser(unittest.TestCase):
 def test_values_and_formula_rejection(self):
  data=ci.normalize(ci.workbook(workbook()));self.assertEqual(data['registration']['regtypes'][0]['price_minor'],2500);self.assertTrue(data['extras']['items'][0]['taxable'])
  with self.assertRaises(ValueError):ci.workbook(workbook(True))
 def test_rich_sessions_and_explicit_fields(self):
  data=ci.normalize(ci.workbook(workbook(rich=True)));session=data['sessions']['sessions'][0]
  self.assertEqual(session['price_minor'],500);self.assertEqual(session['capacity'],100);self.assertEqual(session['location'],'Main Hall');self.assertIn('09:00',session['start'])
 def test_bounded_and_invalid(self):
  for raw in [b'',b'bad',b'x'*(ci.LIMIT+1)]:
   with self.assertRaises(ValueError):ci.workbook(raw)
class IntakeStorage(unittest.TestCase):
 setUp=tc.CheckoutStorage.setUp;tearDown=tc.CheckoutStorage.tearDown;start=tc.CheckoutStorage.start;stop=tc.CheckoutStorage.stop;request=tc.CheckoutStorage.request;auth_headers=tc.CheckoutStorage.auth_headers
 def test_review_then_idempotent_apply_persistence_and_isolation(self):
  before=len(self.store.list());review=self.request('/api/client-intake/preview',{'file':base64.b64encode(workbook()).decode()},'POST');self.assertEqual(len(self.store.list()),before)
  with self.assertRaises(ValueError):ci.apply(self.store,str(uuid.uuid4()),review['token'])
  result=self.request('/api/client-intake/apply',{'token':review['token']},'POST');again=self.request('/api/client-intake/apply',{'token':review['token']},'POST');self.assertEqual(result['event_id'],again['event_id']);self.assertTrue(again['already_applied']);self.assertEqual(len(self.store.list()),before+1)
  self.stop();self.start();base='/api/events/'+result['event_id'];self.assertEqual(self.request(base+'/registration-page')['regtypes'][0]['price_minor'],2500);self.assertFalse(self.request(base+'/publication')['published'])
 def test_expired_review_rejected(self):
  from psycopg import sql
  review=self.request('/api/client-intake/preview',{'file':base64.b64encode(workbook()).decode()},'POST')
  with self.store.connect() as c:c.execute(sql.SQL("UPDATE {} SET expires=now()-interval '1 second'").format(ci.table(self.store,'client_intake_previews')))
  with self.assertRaises(HTTPError):self.request('/api/client-intake/apply',{'token':review['token']},'POST')
