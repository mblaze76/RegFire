import io,unittest
from pathlib import Path
from PIL import Image
import test_checkout as tc
from test_events import draft
class BadgeTheme(unittest.TestCase):
 setUp=tc.CheckoutStorage.setUp;tearDown=tc.CheckoutStorage.tearDown;start=tc.CheckoutStorage.start;stop=tc.CheckoutStorage.stop;request=tc.CheckoutStorage.request;auth_headers=tc.CheckoutStorage.auth_headers
 def test_parent_selected_logo_only_and_removal(self):
  parent=self.request('/api/events',draft(),'POST');other=self.request('/api/events',draft(),'POST');base='/api/events/'+parent['id'];flows=self.request(base+'/flows',{'action':'create','name':'Exhibitor','kind':'exhibitor'},'POST');child=next(f['id'] for f in flows if f['id']!=parent['id'])
  png=io.BytesIO();Image.new('RGB',(120,40),'orange').save(png,format='PNG');asset=self.store.save_asset(parent['id'],'logo',png.getvalue(),Path(self.upload_tmp.name));unused=self.store.save_asset(parent['id'],'logo',png.getvalue(),Path(self.upload_tmp.name))
  page=self.request(base+'/welcome-page');page=self.request(base+'/welcome-page',page|{'logo_asset_id':asset['id']},'PUT');appearance=self.request('/api/events/'+child+'/registration-page')['appearance'];self.assertEqual(appearance['event_logo_asset_id'],asset['id']);self.assertIsNotNone(self.store.asset(child,asset['id']));self.assertIsNone(self.store.asset(child,unused['id']));self.assertIsNone(self.store.asset(other['id'],asset['id']))
  self.request(base+'/welcome-page',page|{'logo_asset_id':None},'PUT');self.assertIsNone(self.store.asset(child,asset['id']));self.assertIsNone(self.request('/api/events/'+child+'/registration-page')['appearance']['event_logo_asset_id'])
