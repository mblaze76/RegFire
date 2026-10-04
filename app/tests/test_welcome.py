import io, sys, uuid, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_events
from test_events import draft
from welcome import validate
from PIL import Image
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

class WelcomeValidation(unittest.TestCase):
    def test_font_catalog_and_validation(self):
        import json
        catalog=json.loads((Path(__file__).resolve().parents[1]/'static/welcome-fonts.json').read_text())
        self.assertEqual(len(catalog),1950)
        for font in [*catalog,'default','arial','georgia','trebuchet','verdana']:
            self.assertEqual(validate({'about_font':font})['about_font'],font)
        for font in ['made-up',[],None,'google-evil;display:none']:
            with self.assertRaises(ValueError):validate({'about_font':font})

    def test_body_color_validation(self):
        self.assertEqual(validate({})['about_color'],'#24242a')
        self.assertEqual(validate({'about_color':'#123ABC'})['about_color'],'#123abc')
        for color in ('white','red;display:none','#123',None):
            with self.assertRaises(ValueError):validate({'about_color':color})

    def test_dashboard_url_validation(self):
        for value in ('javascript:alert(1)','/login','https://','https://bad host.test','https://user:password@example.test','https://example.test:wrong'):
            with self.subTest(value=value), self.assertRaises(ValueError):validate({'login_url':value})
        self.assertEqual(validate({'login_url':' https://dashboard.example.test/login?event=expo '})['login_url'],'https://dashboard.example.test/login?event=expo')
        self.assertEqual(validate({'login_url':''})['login_url'],'')

    def test_limits_links_and_types(self):
        for bad in ({'sponsor_asset_ids':['x']*5},{'about':'a'*10001},{'logo_url':'javascript:alert(1)'},{'sponsor_asset_ids':[str(uuid.uuid4())],'sponsor_urls':[]}):
            with self.assertRaises(ValueError):validate(bad)
        self.assertEqual(validate({'about':'Line 1\nLine 2'})['about'],'Line 1\nLine 2')

class WelcomePersistence(unittest.TestCase):
    setUp=test_events.PostgresTest.setUp
    start=test_events.PostgresTest.start
    stop=test_events.PostgresTest.stop
    tearDown=test_events.PostgresTest.tearDown
    auth_headers=test_events.PostgresTest.auth_headers
    request=test_events.PostgresTest.request
    def test_white_colors_replace_red_and_survive_reopen_restart(self):
        event=self.request('/api/events',draft(),'POST');path='/api/events/'+event['id']+'/welcome-page'
        page=self.request(path)
        page.update(about='Keep event copy',about_font='trebuchet',about_color='#df1666',title_color='#a60000',background_fade=0)
        page=self.request(path,page,'PUT')
        page.update(about_color='#ffffff',title_color='#ffffff')
        saved=self.request(path,page,'PUT')
        self.assertEqual(self.request(path),saved)
        self.stop();self.start()
        reopened=self.request(path)
        self.assertEqual(reopened,saved)
        self.assertEqual(reopened['about_color'],'#ffffff')
        self.assertEqual(reopened['title_color'],'#ffffff')
        self.assertEqual(reopened['about'],'Keep event copy')
        self.assertEqual(reopened['about_font'],'trebuchet')
        self.assertEqual(reopened['background_fade'],0)

    def test_welcome_upload_replace_remove_restart(self):
        event=self.request('/api/events',draft(),'POST');before=self.store.list();base='/api/events/'+event['id']
        png=io.BytesIO();Image.new('RGBA',(80,40),(30,70,140,255)).save(png,format='PNG')
        def upload(event_id):
            req=Request(self.url+'/api/events/'+event_id+'/assets/logo',data=png.getvalue(),method='POST',headers=self.auth_headers()|{'Content-Type':'image/png'})
            import json
            with build_opener(ProxyHandler({})).open(req) as r:return json.load(r)['id']
        logos=[upload(event['id']) for _ in range(6)]
        page={'about_color':'#123abc','about':'Temporary test details\nSecond paragraph'+(' long text '*100),'logo_asset_id':logos[0],'logo_url':'https://example.test/show','sponsor_asset_ids':logos[1:5],'sponsor_urls':['https://example.test/sponsor']*4}
        self.request(base+'/welcome-page',page,'PUT')
        with self.assertRaises(HTTPError) as err:self.request(base+'/welcome-page',page|{'sponsor_asset_ids':logos[1:6],'sponsor_urls':['']*5},'PUT')
        self.assertEqual(err.exception.code,400)
        page['sponsor_asset_ids'][0]=logos[5];self.request(base+'/welcome-page',page,'PUT')
        self.stop();self.start()
        saved=self.request(base+'/welcome-page');self.assertEqual(saved['sponsor_asset_ids'],page['sponsor_asset_ids']);self.assertEqual(saved['about'],page['about']);self.assertEqual(saved['about_color'],'#123abc')
        page.update(logo_asset_id=None,sponsor_asset_ids=[],sponsor_urls=[],about='')
        self.request(base+'/welcome-page',page,'PUT');self.assertEqual(self.request(base+'/welcome-page')['sponsor_asset_ids'],[])
        other=self.request('/api/events',draft(),'POST')
        with self.assertRaises(HTTPError):self.request('/api/events/'+other['id']+'/welcome-page',page|{'logo_asset_id':logos[0]},'PUT')
        self.assertEqual(next(x for x in self.store.list() if x['id']==event['id']),before[0])

    def test_dashboard_destination_persists_per_event(self):
        first=self.request('/api/events',draft(),'POST');second=self.request('/api/events',draft(),'POST')
        path='/api/events/'+first['id']+'/welcome-page'
        url='https://dashboard.example.test/login?event=expo'
        self.request(path,{'login_url':url},'PUT')
        self.stop();self.start()
        self.assertEqual(self.request(path)['login_url'],url)
        self.assertFalse(self.request('/api/events/'+second['id']+'/welcome-page').get('login_url'))
        self.request(path,{'login_url':''},'PUT');self.assertEqual(self.request(path)['login_url'],'')

    def test_independent_buttons_migration_and_destinations(self):
        event=self.request('/api/events',draft(),'POST');base='/api/events/'+event['id'];page=self.request(base+'/welcome-page')
        self.assertEqual(page['buttons'],[dict(id=event['id'],label='Attendee',flow_id=event['id'])])
        flows=self.request(base+'/flows',{'action':'create','name':'Exhibitor','kind':'exhibitor'},'POST');other=next(f for f in flows if f['id']!=event['id'])
        page.update(title='Welcome to Ignite',title_font='google-abeezee',title_color='#123abc',about_font='google-montserrat',about='Keep this text exactly.');page['buttons'][0].update(label='Get your pass',flow_id=other['id'])
        self.request(base+'/welcome-page',page,'PUT')
        self.request(base+'/flows',{'action':'rename','id':other['id'],'name':'Partners'},'POST')
        self.stop();self.store.initialize();self.start()
        saved=self.request(base+'/welcome-page');self.assertEqual(saved['buttons'],page['buttons']);self.assertEqual(saved['title'],'Welcome to Ignite');self.assertEqual(saved['title_font'],'google-abeezee');self.assertEqual(saved['title_color'],'#123abc');self.assertEqual(saved['about_font'],'google-montserrat');self.assertEqual(saved['about'],page['about'])
        stranger=self.request('/api/events',draft(),'POST')
        with self.assertRaises(HTTPError):self.request(base+'/welcome-page',saved|{'buttons':[dict(id=str(uuid.uuid4()),label='Wrong event',flow_id=stranger['id'])]},'PUT')
        self.request(base+'/flows',{'action':'remove','id':other['id'],'confirm_name':'Partners'},'POST')
        self.assertEqual(self.request(base+'/welcome-page')['buttons'],page['buttons'])
        self.assertNotIn(other['id'],[f['id'] for f in self.request(base+'/flows')])
        with self.store.connect() as conn:
            from psycopg import sql
            conn.execute(sql.SQL("UPDATE {} SET body=body-'buttons' WHERE event_id=%s").format(sql.Identifier(self.schema,'welcome_pages')),(event['id'],))
        self.store.initialize();migrated=self.request(base+'/welcome-page');self.assertEqual(migrated['about'],page['about']);self.assertEqual(migrated['buttons'][0]['flow_id'],event['id'])

    def test_welcome_background_isolation_reload_remove(self):
        event=self.request('/api/events',draft(),'POST');other=self.request('/api/events',draft(),'POST');base='/api/events/'+event['id']
        png=io.BytesIO();Image.new('RGB',(100,60),(180,100,30)).save(png,format='PNG')
        import json
        req=Request(self.url+base+'/assets/background',data=png.getvalue(),method='POST',headers=self.auth_headers()|{'Content-Type':'image/png'})
        with build_opener(ProxyHandler({})).open(req) as r:asset=json.load(r)['id']
        page=self.request(base+'/welcome-page');page.update(background_asset_id=asset,background_fade=35,about='Preserve content',about_font='google-montserrat',about_color='#123abc')
        self.request(base+'/welcome-page',page,'PUT');self.stop();self.start()
        saved=self.request(base+'/welcome-page');self.assertEqual(saved['background_asset_id'],asset);self.assertEqual(saved['background_fade'],35);self.assertEqual(saved['buttons'],page['buttons']);self.assertEqual(saved['about'],page['about'])
        self.assertIsNone(self.request(base+'/registration-page').get('appearance',{}).get('background_asset_id'))
        with self.assertRaises(HTTPError):self.request('/api/events/'+other['id']+'/welcome-page',page,'PUT')
        for fade in (-1,101,True,'35'):
            with self.assertRaises(HTTPError):self.request(base+'/welcome-page',page|{'background_fade':fade},'PUT')
        self.request(base+'/welcome-page',page|{'background_asset_id':None},'PUT');self.assertIsNone(self.request(base+'/welcome-page')['background_asset_id'])
