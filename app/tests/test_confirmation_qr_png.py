"""No provider calls: verify the email QR's payload and lossless module rendering."""
import io
import json
import unittest
from unittest.mock import patch
from PIL import Image
from reportlab.graphics.barcode.qr import QrCodeWidget
import confirmation

class EmailQRArtwork(unittest.TestCase):
 def test_identifiers_only_and_scannable_geometry(self):
  event='11111111-1111-4111-8111-111111111111'
  ident='22222222-2222-4222-8222-222222222222'
  with patch('reportlab.graphics.barcode.qr.QrCodeWidget', wraps=QrCodeWidget) as widget:
   raw=confirmation.qr_png(event,ident)
  payload=widget.call_args.args[0]
  self.assertEqual(json.loads(payload),{'event_id':event,'confirmation_id':ident})
  expected=QrCodeWidget(payload,barLevel='M');expected.qr.make()
  with Image.open(io.BytesIO(raw)) as image:
   self.assertEqual(image.format,'PNG')
   self.assertEqual(image.size,((len(expected.qr.modules)+8)*6,)*2)
   self.assertEqual(set(image.getdata()),{(0,0,0),(255,255,255)})
   # Four full white modules on every edge, with no resampling gray pixels.
   for box in [(0,0,image.width,24),(0,image.height-24,image.width,image.height),(0,0,24,image.height),(image.width-24,0,image.width,image.height)]:
    self.assertEqual(image.crop(box).getextrema(),((255,255),)*3)
   for y,row in enumerate(expected.qr.modules):
    for x,dark in enumerate(row):
     self.assertEqual(image.getpixel(((x+4)*6+3,(y+4)*6+3)),(0,0,0) if dark else (255,255,255))
  self.assertLess(len(raw),100000)
