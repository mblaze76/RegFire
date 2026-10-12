"""Transport contracts only; no actual provider requests or email delivery."""
import json, os, unittest
from unittest.mock import Mock, patch
from communications_providers import BirdEmailAdapter, SendGridAdapter, DeliveryError

class EmailHTMLTests(unittest.TestCase):
 def adapter(self,kind):
  client=Mock();client.request.return_value=(202,{},b'{"id":"synthetic","status":"accepted"}')
  return kind(dict(sender='sender@example.test',sender_name='RegFire',api_key='bk_us1_synthetic_private_0123456789'),client),client
 @patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'1'})
 def test_multipart_preserves_plain_text(self):
  for kind in (BirdEmailAdapter,SendGridAdapter):
   with self.subTest(provider=kind.__name__):
    adapter,client=self.adapter(kind);adapter.submit('to@example.test','Confirmation','Readable fallback',html='<p>Styled confirmation</p>')
    payload=json.loads(client.request.call_args.args[1])
    if kind is BirdEmailAdapter:
     self.assertEqual(payload['text'],'Readable fallback');self.assertEqual(payload['html'],'<p>Styled confirmation</p>')
    else:self.assertEqual(payload['content'],[dict(type='text/plain',value='Readable fallback'),dict(type='text/html',value='<p>Styled confirmation</p>')])
 @patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'1'})
 def test_invalid_html_never_contacts_provider(self):
  for kind in (BirdEmailAdapter,SendGridAdapter):
   for value in ('', '  ', {}, 17):
    adapter,client=self.adapter(kind)
    with self.assertRaises(DeliveryError):adapter.submit('to@example.test','Confirmation','Fallback',html=value)
    client.request.assert_not_called()
 @patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'0'})
 def test_bird_html_retains_live_gate(self):
  adapter,client=self.adapter(BirdEmailAdapter)
  with self.assertRaises(DeliveryError):adapter.submit('to@example.test','Confirmation','Fallback',html='<p>Confirmation</p>')
  client.request.assert_not_called()
 @patch.dict(os.environ,{'REGFIRE_COMMUNICATIONS_LIVE':'1'})
 def test_inline_images_use_cid_and_keep_bytes(self):
  import base64
  png=b'\x89PNG\r\n\x1a\nsynthetic'
  for kind in (BirdEmailAdapter,SendGridAdapter):
   adapter,client=self.adapter(kind)
   adapter.submit('to@example.test','Confirmation','Fallback',html='<img src="cid:qr">',inline_images=[dict(content_id='qr',data=png)])
   a=json.loads(client.request.call_args.args[1])['attachments'][0]
   self.assertEqual(a['content_id'],'qr');self.assertEqual(base64.b64decode(a['content']),png)
   self.assertEqual(a['content_type' if kind is BirdEmailAdapter else 'type'],'image/png')
   if kind is SendGridAdapter:self.assertEqual(a['disposition'],'inline')
 def test_invalid_inline_images_do_not_send(self):
  png=b'\x89PNG\r\n\x1a\nsynthetic'
  invalid=[{},[dict(content_id='../file',data=png)],[dict(content_id='qr',data='/private/file')],[dict(content_id='qr',data=b'<svg/>')],[dict(content_id='qr',data=png)]*2,[dict(content_id='qr',data=png+b'x'*(5*1024*1024))]]
  for kind in (BirdEmailAdapter,SendGridAdapter):
   for images in invalid:
    adapter,client=self.adapter(kind)
    with self.assertRaises(DeliveryError):adapter.submit('to@example.test','Confirmation','Fallback',html='<p>Hi</p>',inline_images=images)
    client.request.assert_not_called()
