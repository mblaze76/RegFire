import unittest,uuid
import test_events
from test_events import draft
from sessions import validate,import_preview
from urllib.error import HTTPError

def session(**changes):
    return dict(id=str(uuid.uuid4()),title='Opening keynote',start='2026-10-15T09:00',end='2026-10-15T10:00',price_minor=0,track='Keynotes',speaker='Alex Morgan',location='Main stage',description='Welcome')|changes

class SessionsValidation(unittest.TestCase):
    def test_times_prices_and_ids(self):
        for changes in [dict(end='2026-10-15T08:00'),dict(start='2026-03-08T02:30'),dict(start='2026-11-01T01:30',end='2026-11-01T03:00'),dict(price_minor=True),dict(price_minor=-1),dict(price_minor=2.5),dict(title=''),dict(id='bad'),dict(end='2026-10-16T10:00')]:
            with self.subTest(changes=changes),self.assertRaises(ValueError): validate(dict(sessions=[session(**changes)]),draft())
        row=session()
        with self.assertRaises(ValueError):validate(dict(sessions=[row,row]),draft())
        result=validate(dict(sessions=[row]),draft())
        self.assertEqual(result['sessions'][0]['start_utc'],'2026-10-15T13:00:00+00:00')
    def test_credits_optional_zero_fractional_validation(self):
        for value in (None,0,1.25,10000):
            self.assertEqual(validate(dict(sessions=[session(credits=value)]),draft())['sessions'][0]['credits'],value)
        for value in (-1,1.001,True,'1',float('nan'),float('inf'),10001):
            with self.subTest(value=value),self.assertRaises(ValueError):validate(dict(sessions=[session(credits=value)]),draft())
        result=import_preview(dict(content='title,date,start_time,end_time,credits\nWorkshop,2026-10-15,09:00,10:00,1.25\n',mapping={k:k for k in ('title','date','start_time','end_time','credits')}),draft()|dict(id=str(uuid.uuid4())),'USD')
        self.assertEqual(result['sessions'][0]['credits'],1.25)

    def test_import_mapping_errors_and_precision(self):
        event=draft()|dict(id=str(uuid.uuid4()))
        content='Name\tDay\tFrom\tTo\tCost\n"Keynote, welcome"\t2026-10-15\t09:00\t10:00\t25.50\n'
        mapping=dict(title='Name',date='Day',start_time='From',end_time='To',price='Cost')
        result=import_preview(dict(content=content,mapping=mapping),event,'USD')
        self.assertEqual(result['errors'],[]);self.assertEqual(result['sessions'][0]['price_minor'],2550)
        self.assertEqual(result,import_preview(dict(content=content,mapping=mapping),event,'USD'))
        result=import_preview(dict(content=content.replace('25.50','nan'),mapping=mapping),event,'USD')
        self.assertEqual(result['errors'][0]['row'],2)
        with self.assertRaises(ValueError):import_preview(dict(content='a,a\n1,2'),event,'USD')
        with self.assertRaises(ValueError):import_preview(dict(content=content,mapping=mapping|dict(end_time='From')),event,'USD')
        result=import_preview(dict(content=content,mapping=mapping),event,'JPY');self.assertEqual(len(result['errors']),1)

class SessionsStorage(unittest.TestCase):
    setUp=test_events.PostgresTest.setUp;tearDown=test_events.PostgresTest.tearDown;start=test_events.PostgresTest.start;stop=test_events.PostgresTest.stop;request=test_events.PostgresTest.request;auth_headers=test_events.PostgresTest.auth_headers
    def test_attendee_page_route_is_html(self):
        from urllib.request import Request,build_opener,ProxyHandler
        req=Request(self.url+'/sessions',headers=self.auth_headers())
        with build_opener(ProxyHandler({})).open(req) as response:
            self.assertEqual(response.status,200)
            self.assertIn('sessions-attendee',response.read().decode())

    def test_independent_flow_revision_import_restart_delete(self):
        first=self.request('/api/events',draft(),'POST');other=self.request('/api/events',draft(),'POST')
        base='/api/events/'+first['id'];path=base+'/sessions'
        flows=self.request(base+'/flows',dict(name='Exhibitor',kind='exhibitor'),'POST');child=next(f['id'] for f in flows if f['name']=='Exhibitor')
        page=self.request(path);row=session();page['sessions']=[row]
        saved=self.request(path,page,'PUT');self.assertEqual(saved['revision'],1)
        child_path='/api/events/'+child+'/sessions'
        child_page=self.request(child_path)
        self.assertEqual(child_page['sessions'],[])
        child_page['sessions']=[session(title='Exhibitor only',credits=1.25)]
        child_saved=self.request(child_path,child_page,'PUT')
        self.assertEqual(self.request(path),saved)
        self.assertEqual(self.request(child_path)['sessions'][0]['credits'],1.25)
        self.assertEqual(self.request('/api/events/'+other['id']+'/sessions')['sessions'],[])
        with self.assertRaises(HTTPError):self.request(path,page,'PUT')
        imported=dict(content='title,date,start_time,end_time,price\nWorkshop,2026-10-15,11:00,12:00,50\n',mapping={k:k for k in ('title','date','start_time','end_time','price')})
        preview=self.request(path+'/import-preview',imported,'POST')
        self.assertEqual(len(self.request(path)['sessions']),1)
        with self.assertRaises(HTTPError):self.request(path+'/import',imported|dict(revision=1,digest='wrong'),'POST')
        saved=self.request(path+'/import',imported|dict(revision=1,digest=preview['digest']),'POST');self.assertEqual(len(saved['sessions']),2)
        with self.assertRaises(HTTPError):self.request(path+'/import',imported|dict(revision=2,digest=preview['digest']),'POST')
        self.stop();self.start();self.assertEqual(self.request(path),saved);self.assertEqual(self.request(child_path),child_saved)
        saved['sessions'][0]['title']='Edited';saved=self.request(path,saved,'PUT');self.assertEqual(saved['sessions'][0]['title'],'Edited')
        saved['sessions']=saved['sessions'][1:];saved=self.request(path,saved,'PUT');self.assertEqual(len(saved['sessions']),1)
        self.request(base,dict(confirm_name=first['name']),'DELETE')
        with self.assertRaises(HTTPError):self.request(path)
        self.assertEqual(self.request('/api/events/'+other['id']+'/sessions')['sessions'],[])
