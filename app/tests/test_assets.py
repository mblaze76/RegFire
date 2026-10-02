import sys,io,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image,PngImagePlugin
from assets import normalize_image
class ImageTests(unittest.TestCase):
    def test_valid_image_normalization_and_metadata_removal(self):
        b=io.BytesIO();meta=PngImagePlugin.PngInfo();meta.add_text('private','discard')
        Image.new('RGBA',(3000,1000),'orange').save(b,format='PNG',pnginfo=meta)
        with Image.open(io.BytesIO(normalize_image(b.getvalue()))) as result:
            self.assertEqual(result.format,'PNG');self.assertEqual(result.size,(2560,853));self.assertNotIn('private',result.info)
    def test_invalid_content_and_limits(self):
        for content in (b'<svg></svg>',b'not image',b'',b'x'*(8*1024*1024+1)):
            with self.assertRaises(ValueError):normalize_image(content)
        b=io.BytesIO();Image.new('RGB',(6001,1)).save(b,format='PNG')
        with self.assertRaises(ValueError):normalize_image(b.getvalue())
    def test_animation_rejected(self):
        b=io.BytesIO();Image.new('RGB',(4,4),'red').save(b,format='PNG',save_all=True,append_images=[Image.new('RGB',(4,4),'blue')],duration=100,loop=0)
        with self.assertRaises(ValueError):normalize_image(b.getvalue())
