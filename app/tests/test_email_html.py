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
