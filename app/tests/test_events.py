import secrets
import json, sqlite3, sys, tempfile, threading, unittest, uuid
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Handler, ThreadingHTTPServer, validate
from database import CONFIG, Store
from migrate_sqlite import migrate
from psycopg import sql
from registration import starter, validate_page


def draft():
    return dict(name='Leadership Summit', timezone='America/New_York', format='in_person', start='2026-10-15T09:00', end='2026-10-15T17:00', venue='Main Hall', organizer='Events Team', email='events@example.com')

class ValidationTest(unittest.TestCase):
    def test_invalid_fields(self):
        for changes in ({'name':''}, {'timezone':'Fake/Zone'}, {'email':'invalid'}, {'url':'javascript:alert(1)'}, {'start':'2026-03-08T02:30'}, {'end':'2026-10-15T08:00'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): validate(draft() | changes)
    def test_page_validation(self):
        base = starter(dict(id=str(uuid.uuid4()), name='Example'))
        self.assertEqual(validate_page(base)['currency'], 'USD')
        bad = [dict(title=''), dict(currency='XYZ'), dict(fields=[]), dict(regtypes=[])]
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(ValueError): validate_page(base | changes)
        for price in (-1, 12.5, True, 100000000, '1200'):
            with self.subTest(price=price), self.assertRaises(ValueError):
                validate_page(base | dict(regtypes=[dict(id='attendee',name='Attendee',price_minor=price)]))

    def test_visibility_choices_and_stable_ids(self):
        base=starter(dict(id=str(uuid.uuid4()),name='Example'))
        base['fields'][0]['visible_to']=['attendee']
        self.assertEqual(validate_page(base)['fields'][0]['visible_to'], ['attendee'])
        for refs in ([], ['removed-type'], ['attendee','attendee'], 'attendee'):
            base['fields'][0]['visible_to']=refs
            with self.subTest(refs=refs), self.assertRaises(ValueError): validate_page(base)
        base['fields'][0]['visible_to']=None
        base['fields'][0].update(type='select',options=['A','a'])
        with self.assertRaises(ValueError): validate_page(base)
        base['fields'][0].update(type='text',options=[])
        base['fields'][1]['id']=base['fields'][0]['id']
        with self.assertRaises(ValueError): validate_page(base)

    def test_minimal_draft(self):
        self.assertEqual(validate(dict(name='Planning', timezone='UTC', format='online'))['name'], 'Planning')

@unittest.skipUnless(CONFIG.exists(), 'Local PostgreSQL setup is required for integration checks')
class PostgresTest(unittest.TestCase):
    def setUp(self):
        self.schema = 'regfire_test_' + uuid.uuid4().hex
        self.store = Store(schema=self.schema); self.store.initialize()
        from access import Access
        self.access=Access(self.store);self.password=secrets.token_urlsafe(24);self.access.bootstrap('test-owner@example.test',self.password)
        self.upload_tmp=tempfile.TemporaryDirectory()
        self.start()
    def start(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); self.server.store = Store(schema=self.schema); self.server.upload_root=Path(self.upload_tmp.name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.raw_session=self.access.login('test-owner@example.test',self.password);self.csrf=self.access.session(self.raw_session)['csrf']
    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
    def tearDown(self):
        self.stop()
        with self.store.connect() as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.upload_tmp.cleanup()
    def auth_headers(self):
        return {'Cookie':'regfire_session_'+str(self.server.server_port)+'='+self.raw_session,'X-CSRF-Token':self.csrf,'Origin':self.url}
    def request(self, path, data=None, method='GET', headers=None):
        req = Request(self.url + path, data=json.dumps(data).encode() if data is not None else None, method=method, headers=self.auth_headers() | (headers or {'Content-Type':'application/json'}))
        with build_opener(ProxyHandler({})).open(req, timeout=10) as response: return json.load(response)
    def test_membership_import_lookup_isolation_and_restart(self):
        from membership import starter as membership_starter
        first=self.request('/api/events',draft(),'POST');second=self.request('/api/events',draft(),'POST')
        base='/api/events/'+first['id']+'/membership';other='/api/events/'+second['id']+'/membership'
        config=membership_starter()|dict(enabled=True,regtype_ids=['attendee'])
        self.request(base,config,'PUT')
        data=dict(csv='member_id,email,active,expires\n001,a@example.test,true,2099-12-31\n002,b@example.test,false,\n',mapping={k:k for k in ('member_id','email','active','expires')})
        preview=self.request(base+'/import-preview',data,'POST');self.assertEqual(preview['count'],2)
        self.request(base+'/import',data|dict(digest=preview['digest'],revision=preview['revision']),'POST')
        with self.assertRaises(HTTPError):self.request(base+'/import',data|dict(digest=preview['digest'],revision='stale'),'POST')
        with self.assertRaises(HTTPError):self.request(base+'/import-preview',data|{'csv':data['csv']+'001,c@example.test,true,\n'},'POST')
        self.assertEqual(self.request(base)['import_info']['count'],2)
        result=self.request(base+'/lookup',dict(member_id='001',regtype_id='attendee'),'POST');self.assertEqual(result['status'],'verified');self.assertNotIn('email',result)
        self.assertEqual(self.request(base+'/lookup',dict(member_id='002',regtype_id='attendee'),'POST')['status'],'inactive')
        config['policy']='pending';self.request(base,config,'PUT')
        self.assertEqual(self.request(base+'/lookup',dict(member_id='missing',regtype_id='attendee'),'POST')['status'],'pending')
        self.assertEqual(self.request(other)['import_info']['count'],0);self.assertFalse(self.request(other)['config']['enabled'])
        self.stop();self.start();base='/api/events/'+first['id']+'/membership'
        self.assertEqual(self.request(base)['import_info']['count'],2)
        reg=self.request('/api/events/'+first['id']+'/registration-page');reg['regtypes'][0]['id']='replacement'
        with self.assertRaises(HTTPError):self.request('/api/events/'+first['id']+'/registration-page',reg,'PUT')
    def test_membership_api_fixture_and_host_guard(self):
        from membership import starter as membership_starter
        event=self.request('/api/events',draft(),'POST');base='/api/events/'+event['id']+'/membership'
        config=membership_starter()|dict(enabled=True,source='api',regtype_ids=['attendee']);config['api']['endpoint']='fixture://demo'
        result=self.request(base+'/test',dict(config=config,member_id='DEMO-ACTIVE'),'POST');self.assertTrue(result['connected']);self.assertTrue(result['fixture'])
        self.request(base,config,'PUT')
        self.assertEqual(self.request(base+'/lookup',dict(member_id='DEMO-UNAVAILABLE',regtype_id='attendee'),'POST')['status'],'unavailable')
        with self.assertRaises(HTTPError) as error:self.request('/api/events',headers={'Host':'untrusted.example'})
        self.assertEqual(error.exception.code,403)
    def test_live_preview_accepts_unsaved_regtypes_without_persisting(self):
        event=self.request('/api/events',draft(),'POST');prefix='/api/events/'+event['id']
        reg=self.request(prefix+'/registration-page');reg['regtypes'].append(dict(id='new-unsaved',name='Unsaved type',price_minor=2000))
        demo=self.request(prefix+'/demographics')
        result=self.request(prefix+'/demographics-preview',dict(page=demo,registration_page=reg,answers={},regtype_id='new-unsaved'),'POST')
        self.assertEqual(result['visible_ids'],[])
        self.assertEqual(len(self.request(prefix+'/registration-page')['regtypes']),1)

    def test_delete_event_cascades_and_preserves_other_events(self):
        from membership import starter as membership_starter
        first=self.request('/api/events',draft(),'POST');other=self.request('/api/events',draft()|{'name':'Keep this event'},'POST');prefix='/api/events/'+first['id']
        reg=self.request(prefix+'/registration-page');self.request(prefix+'/registration-page',reg,'PUT')
        demo=self.request(prefix+'/demographics');self.request(prefix+'/demographics',demo,'PUT')
        self.request(prefix+'/membership',membership_starter(),'PUT')
        with self.assertRaises(HTTPError):self.request(prefix,{'confirm_name':'wrong name'},'DELETE')
        self.assertEqual(len(self.request('/api/events')),2)
        self.request(prefix,{'confirm_name':first['name']},'DELETE')
        self.assertEqual([e['id'] for e in self.request('/api/events')],[other['id']])
        for suffix in ['/registration-page','/demographics','/membership']:
            with self.assertRaises(HTTPError):self.request(prefix+suffix)
        with self.store.connect() as conn:
            for name in ['registration_pages','demographics_pages','membership_settings','membership_imports','registration_assets']:
                self.assertEqual(conn.execute(sql.SQL('SELECT count(*) FROM {} WHERE event_id=%s').format(sql.Identifier(self.schema,name)),(first['id'],)).fetchone()[0],0)
        with self.assertRaises(HTTPError):self.request(prefix,{'confirm_name':first['name']},'DELETE')
    def test_structured_address_preserves_legacy_location_and_line_two(self):
        address=dict(line1='123 Example Street',line2='Suite 4',city='Sample City',region='New York',postal='10001',country='United States')
        event=self.request('/api/events',draft()|dict(location='Legacy free-form location',address=address),'POST')
        self.assertEqual(event['location'],'Legacy free-form location');self.assertEqual(event['address'],address)
        event=self.request('/api/events/'+event['id'],event|{'name':'Edited address event'},'PUT')
        self.assertEqual(event['address']['line2'],'Suite 4')
        with self.assertRaises(HTTPError):self.request('/api/events/'+event['id'],event|{'address':[]},'PUT')
        self.assertEqual(self.request('/api/events')[0]['address'],address)

    def test_create_edit_reload_and_app_restart(self):
        saved = self.request('/api/events', draft(), 'POST')
        self.assertEqual(saved['status'], 'draft'); self.assertEqual(len(self.request('/api/events')), 1)
        saved.update(name='Updated Summit', format='online', url='https://example.com/join')
        edited = self.request('/api/events/' + saved['id'], saved, 'PUT')
        self.assertEqual(edited['id'], saved['id']); self.stop(); self.start()
        loaded = self.request('/api/events'); self.assertEqual(len(loaded), 1); self.assertEqual(loaded[0]['name'], 'Updated Summit'); self.assertEqual(loaded[0]['url'], 'https://example.com/join')
        with self.store.connect() as conn:
            self.assertEqual(conn.execute(sql.SQL('SELECT body->>\'name\' FROM {} WHERE id=%s').format(self.store.table()), (saved['id'],)).fetchone()[0], 'Updated Summit')
    def test_invalid_save_does_not_change_database(self):
        data = draft(); data['end'] = '2026-10-15T08:00'
        with self.assertRaises(HTTPError) as error: self.request('/api/events', data, 'POST')
        self.assertEqual(error.exception.code, 400); self.assertEqual(self.request('/api/events'), [])
    def test_missing_edit_does_not_insert(self):
        with self.assertRaises(HTTPError) as error: self.request('/api/events/' + str(uuid.uuid4()), draft(), 'PUT')
        self.assertEqual(error.exception.code, 404); self.assertEqual(self.request('/api/events'), [])
    def test_cross_origin_rejected(self):
        with self.assertRaises(HTTPError) as error: self.request('/api/events', draft(), 'POST', {'Origin':'https://example.com'})
        self.assertEqual(error.exception.code, 403)
    def test_registration_page_edit_order_isolation_and_restart(self):
        a=self.request('/api/events',draft(),'POST')
        b=self.request('/api/events',draft() | {'name':'Separate event'},'POST')
        path='/api/events/'+a['id']+'/registration-page'
        page=self.request(path)
        self.assertIsNone(page['updated'])
        page.update(title='Join the summit', intro='Welcome', currency='USD')
        page['regtypes']=[dict(id='speaker',name='Speaker',price_minor=0),dict(id='delegate',name='Delegate',price_minor=12599)]
        page['fields'].append(dict(id='topic',label='Talk topic',type='select',required=True,options=['Design','Engineering'],visible_to=['speaker']))
        page['fields']=list(reversed(page['fields']))
        saved=self.request(path,page,'PUT')
        self.assertEqual(saved['fields'][0]['id'],'topic')
        self.assertEqual(saved['regtypes'][1]['price_minor'],12599)
        self.assertEqual(saved['fields'][0]['visible_to'],['speaker'])
        saved['regtypes'].reverse(); saved['regtypes'][0]['name']='Professional'; saved['fields'].pop(1)
        saved=self.request(path,saved,'PUT')
        self.stop();self.start()
        self.assertEqual(self.request(path),saved)
        other=self.request('/api/events/'+b['id']+'/registration-page')
        self.assertIsNone(other['updated']);self.assertEqual(other['regtypes'][0]['name'],'Attendee')
        self.assertEqual(self.request('/api/events')[1]['name'],a['name'])

    def test_page_rejects_stale_types_and_invalid_price_atomically(self):
        a=self.request('/api/events',draft(),'POST');path='/api/events/'+a['id']+'/registration-page'
        page=self.request(path);page['fields'][0]['visible_to']=['attendee']
        saved=self.request(path,page,'PUT')
        for changes in (dict(regtypes=[dict(id='new',name='New',price_minor=0)]),dict(regtypes=[dict(id='attendee',name='Attendee',price_minor=1.25)])):
            with self.assertRaises(HTTPError) as error:self.request(path,saved | changes,'PUT')
            self.assertEqual(error.exception.code,400);self.assertEqual(self.request(path),saved)
        saved['fields'][0]['visible_to']=None;saved['regtypes']=[dict(id='new',name='New',price_minor=75)]
        updated=self.request(path,saved,'PUT');self.assertEqual(updated['regtypes'][0]['id'],'new')

    def test_page_missing_event_and_cross_origin(self):
        path='/api/events/'+str(uuid.uuid4())+'/registration-page'
        for method in ('GET','PUT'):
            with self.assertRaises(HTTPError) as error:self.request(path,starter(dict(id='unused',name='Example')) if method=='PUT' else None,method)
            self.assertEqual(error.exception.code,404)
        a=self.request('/api/events',draft(),'POST');path='/api/events/'+a['id']+'/registration-page'
        with self.assertRaises(HTTPError) as error:self.request(path,self.request(path),'PUT',{'Origin':'https://example.com'})
        self.assertEqual(error.exception.code,403)

    def test_additive_schema_initialization_preserves_events(self):
        a=self.request('/api/events',draft(),'POST')
        before=self.request('/api/events')
        self.store.initialize();self.store.initialize()
        self.assertEqual(self.request('/api/events'),before)
        with self.store.connect() as conn:
            refs=conn.execute("SELECT count(*) FROM pg_constraint WHERE conrelid=%s::regclass AND contype='f'", (self.schema+'.registration_pages',)).fetchone()[0]
            self.assertEqual(refs,1)

    def test_date_rates_api_persistence_and_legacy_read(self):
        event=self.request('/api/events',draft(),'POST');path='/api/events/'+event['id']+'/registration-page'
        data=self.request(path);data['regtypes'][0].update(price_minor=25000,use_default=False,rates=[dict(id='early',name='Early bird',price_minor=12550,start='2026-10-01T09:00',end='2026-10-02T09:00')])
        saved=self.request(path,data,'PUT')
        preview_path='/api/events/'+event['id']+'/pricing-preview'
        evaluated=self.request(preview_path,dict(page=saved,at='2026-10-01T09:00'),'POST')
        self.assertEqual(evaluated['timezone'],'America/New_York');self.assertEqual(evaluated['regtypes']['attendee']['price_minor'],12550)
        self.assertEqual(self.request(preview_path,dict(page=saved,at='2026-10-02T09:00'),'POST')['regtypes']['attendee']['status'],'unavailable')
        self.stop();self.start();self.assertEqual(self.request(path),saved)
        import copy
        invalid=copy.deepcopy(saved);invalid['regtypes'][0]['rates'].append(dict(id='overlap',name='Overlap',price_minor=999,start='2026-10-01T10:00',end='2026-10-02T12:00'))
        with self.assertRaises(HTTPError) as error:self.request(path,invalid,'PUT')
        self.assertEqual(error.exception.code,400);self.assertEqual(self.request(path),saved)
        with self.assertRaises(HTTPError) as error:self.request(preview_path,dict(page=saved,at='bad'),'POST')
        self.assertEqual(error.exception.code,400)
        legacy=starter(event)
        with self.store.connect() as conn:
            from psycopg.types.json import Jsonb
            conn.execute(sql.SQL('UPDATE {} SET body=%s WHERE event_id=%s').format(self.store.page_table()),(Jsonb(legacy),event['id']))
        loaded=self.request(path);self.assertNotIn('rates',loaded['regtypes'][0])
        self.assertEqual(self.request(preview_path,dict(page=loaded,at='2026-10-01T09:00'),'POST')['regtypes']['attendee']['status'],'default')

    def test_timezone_edit_revalidates_rate_periods(self):
        event=self.request('/api/events',draft() | {'timezone':'UTC'},'POST');path='/api/events/'+event['id']+'/registration-page'
        data=self.request(path);data['regtypes'][0]['rates']=[dict(id='dst',name='DST',price_minor=100,start='2026-03-08T02:30',end='2026-03-08T04:00')]
        saved=self.request(path,data,'PUT')
        with self.assertRaises(HTTPError) as error:self.request('/api/events/'+event['id'],event | {'timezone':'America/New_York'},'PUT')
        self.assertEqual(error.exception.code,400);self.assertEqual(self.request('/api/events')[0]['timezone'],'UTC');self.assertEqual(self.request(path),saved)

    def upload(self,event_id,kind,color='orange'):
        import io
        from PIL import Image
        buffer=io.BytesIO();Image.new('RGB',(24,16),color).save(buffer,format='PNG')
        req=Request(self.url+'/api/events/'+event_id+'/assets/'+kind,data=buffer.getvalue(),method='POST',headers=self.auth_headers()|{'Content-Type':'image/png'})
        with build_opener(ProxyHandler({})).open(req,timeout=10) as response:return json.load(response)

    def test_image_upload_replace_remove_fade_and_restart(self):
        event=self.request('/api/events',draft(),'POST');path='/api/events/'+event['id']+'/registration-page'
        logo=self.upload(event['id'],'logo');background=self.upload(event['id'],'background')
        data=self.request(path);data['appearance']=dict(logo_asset_id=logo['id'],background_asset_id=background['id'],background_fade=65)
        saved=self.request(path,data,'PUT');self.stop();self.start();self.assertEqual(self.request(path),saved)
        with build_opener(ProxyHandler({})).open(Request(self.url+logo['url'],headers=self.auth_headers())) as response:
            self.assertEqual(response.headers['Content-Type'],'image/png');self.assertTrue(response.read().startswith(b'\x89PNG'))
        replacement=self.upload(event['id'],'logo','blue');self.assertNotEqual(logo['id'],replacement['id'])
        saved['appearance']['logo_asset_id']=replacement['id'];saved=self.request(path,saved,'PUT');self.assertEqual(saved['appearance']['background_fade'],65)
        saved['appearance'].update(logo_asset_id=None,background_asset_id=None)
        removed=self.request(path,saved,'PUT');self.assertIsNone(removed['appearance']['logo_asset_id'])
        self.assertTrue((self.server.upload_root/(logo['id']+'.png')).exists())

    def test_image_event_isolation_content_and_fade_validation(self):
        a=self.request('/api/events',draft(),'POST');b=self.request('/api/events',draft(),'POST')
        logo=self.upload(a['id'],'logo');path='/api/events/'+b['id']+'/registration-page'
        data=self.request(path);data['appearance']=dict(logo_asset_id=logo['id'],background_asset_id=None,background_fade=80)
        with self.assertRaises(HTTPError) as error:self.request(path,data,'PUT')
        self.assertEqual(error.exception.code,400)
        with self.assertRaises(HTTPError) as error:self.request('/api/events/'+b['id']+'/assets/'+logo['id'])
        self.assertEqual(error.exception.code,404)
        data['appearance']=dict(background_fade=101)
        with self.assertRaises(HTTPError) as error:self.request(path,data,'PUT')
        self.assertEqual(error.exception.code,400)
        req=Request(self.url+'/api/events/'+a['id']+'/assets/logo',data=b'<svg onload="alert(1)"></svg>',method='POST',headers=self.auth_headers()|{'Content-Type':'image/png'})
        with self.assertRaises(HTTPError) as error:build_opener(ProxyHandler({})).open(req)
        self.assertEqual(error.exception.code,400)

    def test_demographics_persistence_isolation_and_branch_preview(self):
        from test_demographics import sample
        a=self.request('/api/events',draft(),'POST');b=self.request('/api/events',draft(),'POST')
        path='/api/events/'+a['id']+'/demographics'
        self.assertEqual(self.request(path)['questions'],[])
        data=sample();saved=self.request(path,data,'PUT');self.stop();self.start();self.assertEqual(self.request(path),saved)
        self.assertEqual(self.request('/api/events/'+b['id']+'/demographics')['questions'],[])
        result=self.request('/api/events/'+a['id']+'/demographics-preview',dict(page=saved,regtype_id='attendee',answers={'path':'networking','topics':['technology'],'details':'stale'},check=True),'POST')
        self.assertEqual(result['visible_ids'],['path']);self.assertEqual(result['errors'],{})
        self.assertEqual(self.request(path),saved)
        invalid=dict(saved);invalid['questions']=list(reversed(saved['questions']))
        with self.assertRaises(HTTPError) as error:self.request(path,invalid,'PUT')
        self.assertEqual(error.exception.code,400);self.assertEqual(self.request(path),saved)

    def test_demographics_regtype_removal_guard_and_missing_event(self):
        from test_demographics import question,page
        event=self.request('/api/events',draft(),'POST');base='/api/events/'+event['id']
        reg=self.request(base+'/registration-page');reg['regtypes'].append(dict(id='speaker',name='Speaker',price_minor=0));reg=self.request(base+'/registration-page',reg,'PUT')
        demo=page([question('shared',visible=['attendee','speaker'])]);self.request(base+'/demographics',demo,'PUT')
        reg['regtypes']=[reg['regtypes'][0]]
        with self.assertRaises(HTTPError) as error:self.request(base+'/registration-page',reg,'PUT')
        self.assertEqual(error.exception.code,400);self.assertEqual(len(self.request(base+'/registration-page')['regtypes']),2)
        demo['questions'][0]['visible_to']=None;self.request(base+'/demographics',demo,'PUT');self.request(base+'/registration-page',reg,'PUT')
        with self.assertRaises(HTTPError) as error:self.request('/api/events/'+str(uuid.uuid4())+'/demographics')
        self.assertEqual(error.exception.code,404)

    def test_migration_backup_idempotency_and_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'old.sqlite3'
            event_id = str(uuid.uuid4()); now = '2026-09-30T00:00:00+00:00'
            data = validate(draft()) | dict(id=event_id,status='draft',created=now,updated=now)
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE events(id TEXT PRIMARY KEY, body TEXT, updated TEXT)')
                db.execute('INSERT INTO events VALUES(?,?,?)',(event_id,json.dumps(data),now))
            total, added, backup = migrate(path, self.store, Path(tmp) / 'backups')
            self.assertEqual((total,added),(1,1)); self.assertTrue(backup.exists())
            self.assertEqual(migrate(path,self.store,Path(tmp)/'backups')[1],0)
            self.store.save(event_id, validate(draft() | {'name':'New PostgreSQL edit'}),now,True)
            with self.assertRaises(RuntimeError): migrate(path,self.store,Path(tmp)/'backups')
            self.assertEqual(self.store.list()[0]['name'],'New PostgreSQL edit')
            with sqlite3.connect(backup) as db: self.assertEqual(json.loads(db.execute('SELECT body FROM events').fetchone()[0])['name'],'Leadership Summit')

if __name__ == '__main__': unittest.main()
