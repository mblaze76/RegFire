import unittest,copy,uuid,json
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler
from psycopg import sql
from psycopg.types.json import Jsonb
import test_checkout as tc
import publication,publication_snapshot as ps
from checkout import quote_order
class Snapshots(unittest.TestCase):
 setUp=tc.CheckoutStorage.setUp;tearDown=tc.CheckoutStorage.tearDown;start=tc.CheckoutStorage.start;stop=tc.CheckoutStorage.stop;request=tc.CheckoutStorage.request;auth_headers=tc.CheckoutStorage.auth_headers;setup_order=tc.CheckoutStorage.setup_order
 def publish(self,flow):
  state=publication.state(self.store,flow);return publication.state(self.store,flow,dict(published=True,revision=state['revision'],review_digest=state['review_digest']))
 def public(self,path,data=None):
  headers={'Origin':self.url,'Content-Type':'application/json'}
  with build_opener(ProxyHandler({})).open(Request(self.url+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)) as r:return json.load(r)
 def test_draft_config_isolated_and_review_digest_required(self):
  flow,page,data=self.setup_order(1000);self.publish(flow)
  old=self.public('/api/public/events/'+flow+'/flow-preview')
  stale=publication.state(self.store,flow)
  page['regtypes'][0]['price_minor']=3000;page['title']='Draft-only title';self.request('/api/events/'+flow+'/registration-page',page,'PUT')
  welcome=self.request('/api/events/'+flow+'/welcome-page');welcome['title_font']='georgia';welcome['background_color']='#123456';self.request('/api/events/'+flow+'/welcome-page',welcome,'PUT')
  footer=self.request('/api/events/'+flow+'/event-footer');footer['footer']['message']='Draft footer';self.request('/api/events/'+flow+'/event-footer',footer,'PUT')
  public=self.public('/api/public/events/'+flow+'/flow-preview')
  self.assertEqual(public,old)
  self.assertEqual(self.public('/api/public/events/'+flow+'/checkout/quote',data)['grand_total_minor'],1000)
  self.assertEqual(self.request('/api/events/'+flow+'/checkout/quote',data,'POST')['grand_total_minor'],3000)
  with self.assertRaises(ValueError):publication.state(self.store,flow,dict(published=True,revision=stale['revision'],review_digest=stale['review_digest']))
  changes=publication.state(self.store,flow)['changes'];self.assertIn('Shared event branding',changes);self.assertIn('Attendee details and registration prices',changes)
  self.publish(flow);new=self.public('/api/public/events/'+flow+'/flow-preview');self.assertEqual(new['registration']['title'],'Draft-only title');self.assertEqual(new['registration']['appearance']['intro_font'],'georgia');self.assertEqual(new['registration']['appearance']['footer']['message'],'Draft footer')
 def test_current_inventory_and_cross_flow_context(self):
  from test_extra_options import item
  flow,_,data=self.setup_order(0);other,_,_=self.setup_order(500)
  extra=self.request('/api/events/'+flow+'/extra-options');extra['items']=[item(price_minor=0,inventory=1,taxable=False)];self.request('/api/events/'+flow+'/extra-options',extra,'PUT');self.publish(flow)
  data['extras']=[dict(item_id=extra['items'][0]['id'],quantity=1)]
  snap=ps.load(self.store,flow)
  with ps.using(self.store,flow,snap):
   self.assertIsNone(ps.current(self.store,other))
   self.assertEqual(self.store.registration_page(other)['regtypes'][0]['price_minor'],500)
  order=self.request('/api/events/'+flow+'/checkout/save',data,'POST');self.request('/api/checkout/'+order['id']+'/start',{},'POST')
  with self.assertRaises(HTTPError):self.public('/api/public/events/'+flow+'/checkout/quote',data)
  self.assertIsNone(ps.current(self.store,flow))
 def test_legacy_migration_freezes_before_later_edits(self):
  flow,page,_=self.setup_order(1000)
  with self.store.connect() as c:c.execute(sql.SQL('INSERT INTO {}(flow_id,published,revision) VALUES(%s,true,1)').format(sql.Identifier(self.store.schema,'registration_publications')),(flow,))
  self.store.initialize();self.assertIsNotNone(ps.load(self.store,flow))
  page['title']='Later draft';self.request('/api/events/'+flow+'/registration-page',page,'PUT');self.store.initialize()
  self.assertNotEqual(ps.load(self.store,flow)['registration_pages']['title'],'Later draft')
 def test_draft_only_assets_not_public_and_unpublish_closes(self):
  import io
  from PIL import Image
  from pathlib import Path
  flow,_,_=self.setup_order(0);b=io.BytesIO();Image.new('RGB',(20,20),'red').save(b,format='PNG')
  a=self.store.save_asset(flow,'logo',b.getvalue(),Path(self.upload_tmp.name));welcome=self.request('/api/events/'+flow+'/welcome-page');welcome['logo_asset_id']=a['id'];self.request('/api/events/'+flow+'/welcome-page',welcome,'PUT');self.publish(flow)
  b=io.BytesIO();Image.new('RGB',(20,20),'blue').save(b,format='PNG');draft=self.store.save_asset(flow,'logo',b.getvalue(),Path(self.upload_tmp.name))
  self.assertIsNotNone(ps.public_asset(self.store,flow,a['id']));self.assertIsNone(ps.public_asset(self.store,flow,draft['id']))
  state=publication.state(self.store,flow);publication.state(self.store,flow,dict(published=False,revision=state['revision']))
  self.assertIsNone(ps.public_asset(self.store,flow,a['id']))
