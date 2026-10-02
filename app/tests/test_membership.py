import unittest,sys,json,threading
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from membership import *

class MembershipTests(unittest.TestCase):
    def setUp(self):self.config=starter()|dict(enabled=True,regtype_ids=['member'])
    def test_csv_mapping_duplicates_and_atomic_validation(self):
        mapping=dict(zip(FIELDS,['ID','Email','Status','End']))
        rows=parse_csv('ID,Email,Status,End\n001,ME@example.com,active,2026-10-01\n002,,inactive,\n',mapping)
        self.assertEqual(rows[0]['member_id'],'001');self.assertEqual(rows[0]['email'],'me@example.com');self.assertEqual(len(summary(rows)['preview']),2)
        for content in ['ID,Email,Status,End\n001,a@example.com,true,\n001,b@example.com,true,', 'ID,Email,Status,End\n001,A@example.com,true,\n002,a@example.com,true,','ID,Email,Status,End\n1,x@example.com,maybe,','ID,Email,Status,End\n1,x@example.com,true,2026-02-30','ID,Email,Status,End\n,,,','ID,Email,Status,End\n1,a@example.com,true,2026-01-01,extra']:
            with self.subTest(content=content),self.assertRaises(ValueError):parse_csv(content,mapping)
    def test_lookup_policies_and_expiry_in_event_timezone(self):
        r=clean_record(dict(member_id='001',email='ME@example.com',active=True,expires='2026-10-01'))
        self.assertTrue(matches(r,lookup_keys(dict(email='me@EXAMPLE.com'))));self.assertFalse(matches(r,lookup_keys(dict(member_id='002',email='me@example.com'))))
        before=datetime(2026,10,2,3,59,tzinfo=timezone.utc);after=datetime(2026,10,2,4,0,tzinfo=timezone.utc)
        self.assertEqual(outcome(self.config,r,'America/New_York',now=before)['status'],'verified')
        self.assertEqual(outcome(self.config,r,'America/New_York',now=after)['status'],'expired')
        for record,unavailable,reason in [(None,False,'no_match'),(r|{'active':False},False,'inactive'),(None,True,'unavailable')]:
            a=outcome(self.config,record,'UTC',unavailable,after);self.assertEqual(a['status'],reason);self.assertFalse(a['can_continue'])
            b=outcome(self.config|{'policy':'pending'},record,'UTC',unavailable,after);self.assertEqual(b['status'],'pending');self.assertEqual(b['verification_status'],reason);self.assertTrue(b['can_continue']);self.assertIn('not confirmed',b['pricing'])
        self.assertEqual(outcome(self.config,r,'UTC',applies=False)['status'],'not_required')
    def test_configuration_and_target_restrictions(self):
        self.assertFalse(starter()['enabled']);self.assertEqual(validate(self.config,[{'id':'member'}])['regtype_ids'],['member'])
        for ep in ['http://example.com','https://user:pass@example.com','https://example.com:8443/a','https://example.com/?token=x','file:///etc/passwd']:
            with self.assertRaises(ValueError):endpoint(ep)
        for ip in ['127.0.0.1','10.0.0.1','169.254.169.254','::1','::ffff:127.0.0.1']:
            with patch('membership.socket.getaddrinfo',return_value=[(2,1,6,'',(ip,443))]),self.assertRaises(Unavailable):public_addresses('example.com')
        with self.assertRaises(ValueError):validate(self.config,[{'id':'other'}])
    def test_adapter_shape_mapping_local_http_fixture(self):
        class Fixture(BaseHTTPRequestHandler):
            def do_POST(self):
                query=json.loads(self.rfile.read(int(self.headers['Content-Length'])));result={'member':{'identity':{'id':query['member_id'],'email':query['email']},'enabled':True,'end':'2099-01-01'}}
                data=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        c=self.config|{'api':dict(endpoint='https://example.com/lookup',credential_env='',mapping=dict(member_id='identity.id',email='identity.email',active='enabled',expires='end'))}
        def fixture_transport(url,payload,token):
            with urlopen(Request(f'http://127.0.0.1:{server.server_port}/lookup',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})) as r:return json.load(r)
        try:self.assertTrue(api_lookup(c,dict(member_id='M1',email='x@example.com'),fixture_transport)['active'])
        finally:server.shutdown();server.server_close();thread.join()
        for response in [{}, {'member':[]},{'member':{'identity':{'id':'WRONG','email':'x@example.com'},'enabled':True,'end':''}}]:
            with self.assertRaises(Unavailable):api_lookup(c,dict(member_id='M1',email='x@example.com'),lambda *args:response)
        self.assertIsNone(api_lookup(c,dict(member_id='M1',email=''),lambda *args:{'member':None}))
    def test_synthetic_adapter_and_missing_credential(self):
        c=self.config|{'api':starter()['api']|{'endpoint':'fixture://demo'}}
        self.assertTrue(api_lookup(c,lookup_keys({'member_id':'DEMO-ACTIVE'}))['active'])
        with self.assertRaises(Unavailable):api_lookup(c,lookup_keys({'member_id':'DEMO-UNAVAILABLE'}))
        c['api'].update(endpoint='https://example.com',credential_env='REGFIRE_MEMBERSHIP_MISSING_TEST')
        with patch.dict(os.environ,{},clear=True),self.assertRaises(Unavailable):api_lookup(c,lookup_keys({'member_id':'x'}))
    def test_https_no_redirect_and_public_ip_pinning(self):
        from unittest.mock import MagicMock
        response=MagicMock();response.status=302;response.getheader.return_value='application/json';conn=MagicMock();conn.getresponse.return_value=response
        with patch('membership.public_addresses',return_value=['93.184.216.34']),patch('membership.PinnedHTTPS',return_value=conn) as pinned,self.assertRaises(Unavailable):
            https_json('https://example.com/lookup',{'member_id':'x'})
        pinned.assert_called_once_with('example.com','93.184.216.34');self.assertEqual(conn.request.call_count,1);conn.close.assert_called_once()
