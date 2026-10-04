import unittest,uuid,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from background import validate
from registration import starter,validate_page
from welcome import validate as welcome
from event_footer import normalize
class BackgroundChoices(unittest.TestCase):
 def test_legacy_defaults_preserve_images_and_footer(self):
  image=str(uuid.uuid4())
  self.assertEqual(validate({'background_asset_id':image})['background_mode'],'image')
  f=normalize({});self.assertEqual((f['background_color'],f['background_fade']),('#242127',0))
 def test_choice_and_retained_image_across_all_models(self):
  image=str(uuid.uuid4());values=dict(background_mode='color',background_color='#ABCDEF',background_fade=37,background_asset_id=image)
  page=starter(dict(id=str(uuid.uuid4()),name='Test'));page.setdefault('appearance',{}).update(values)
  for result in [validate(values),welcome(values),normalize(values),validate_page(page)['appearance']]:
   for k,v in {**values,'background_color':'#abcdef'}.items():self.assertEqual(result[k],v)
 def test_invalid_background_rejected(self):
  for data in [{'background_mode':'script'},{'background_color':'red'},{'background_fade':101},{'background_fade':True},{'background_asset_id':'bad'}]:
   with self.assertRaises(ValueError):validate(data)
