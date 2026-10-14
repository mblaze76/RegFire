import unittest,copy
import confirmation,confirmation_email

def fixture():
 return dict(settings=copy.deepcopy(confirmation.DEFAULT),event=dict(name='Synthetic Event',start='',end='',timezone='UTC',venue='',location=''),event_id='event',confirmation_id='confirmation',sample=True,sandbox=False,status='sample',paid_minor=0,quote=dict(currency='USD',regtype='Attendee',details=[dict(label='Name',value='<script>bad</script>')],sessions=[dict(title='Session')],lines=[dict(name='Ticket',quantity=1,unit_price_minor=100,line_total_minor=100,kind='registration')],subtotal_minor=100,discount_minor=0,tax_minor=0,grand_total_minor=100))
class EmailPresentation(unittest.TestCase):
 def test_safe_content_sample_and_cid(self):
  doc=fixture();html=confirmation_email.render(doc,{'qr':'confirmation-qr','logo':'event-logo'})
  self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
  self.assertIn('Not valid for entry',html);self.assertIn('cid:confirmation-qr',html)
  self.assertIn('Sample amount (not a payment)',html)
  self.assertNotIn('https://',html)
 def test_saved_layout_toggles_and_real_status(self):
  doc=fixture();doc.update(sample=False,status='confirmed_free');doc['settings'].update(show_sessions=False,show_wallet=False,qr_position='bottom',layout=['receipt','message','attendee','sessions','extras','sponsors'])
  html=confirmation_email.render(doc,{'qr':'qr'})
  self.assertLess(html.index('Receipt'),html.index('Thank you for registering'))
  self.assertGreater(html.index('cid:qr'),html.index('Amount paid'))
  self.assertNotIn('Your registered sessions',html);self.assertNotIn('wallet passes',html)
  self.assertIn('No payment required',html)
 def test_reject_unsafe_links_and_identifiers(self):
  for url in ['javascript:alert(1)','http://example.com','https://user:secret@example.com']:
   with self.assertRaises(ValueError):confirmation_email.render(fixture(),confirmation_url=url)
  with self.assertRaises(ValueError):confirmation_email.render(fixture(),{'qr':'bad" onerror="alert(1)'})

class InlineAssets(unittest.TestCase):
 def test_flow_owned_assets_normalized_and_foreign_rejected(self):
  import tempfile
  from pathlib import Path
  from unittest.mock import Mock
  from PIL import Image
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);Image.new('RGB',(1200,600),'red').save(root/'logo.jpg')
   store=Mock();store.asset.return_value=('logo.jpg',)
   doc=fixture();doc.update(flow_id='flow',appearance={'logo_asset_id':'asset'})
   result=confirmation_email.prepare(doc,store,root)
   store.asset.assert_called_once_with('flow','asset')
   self.assertEqual([a['content_id'] for a in result['inline_images']],['confirmation-qr','event-logo','apple-wallet-preview','google-wallet-preview'])
   import io
   with Image.open(io.BytesIO(result['inline_images'][1]['data'])) as im:self.assertEqual(im.size,(900,450));self.assertEqual(im.format,'PNG')
   store.asset.return_value=None
   with self.assertRaises(ValueError):confirmation_email.prepare(doc,store,root)
   store.asset.return_value=('../outside.png',)
   with self.assertRaises(ValueError):confirmation_email.prepare(doc,store,root)

class CompletePresentation(unittest.TestCase):
 def test_rich_content_identifier_and_no_wallet_links(self):
  doc=fixture();doc['confirmation_id']='20261014';doc['quote']['sessions']=[dict(title='Keynote',start='09:00',end='10:00',location='Hall'),dict(title='Workshop',start='11:00',end='12:00',location='Studio')]
  doc['quote']['lines'] += [dict(name='Shirt — Medium',quantity=2,unit_price_minor=2500,line_total_minor=5000,kind='extra'),dict(name='Shirt — Large',quantity=1,unit_price_minor=2500,line_total_minor=2500,kind='extra')]
  html=confirmation_email.render(doc,{'qr':'qr','apple-wallet':'apple','google-wallet':'google'},'https://registration.example/attendee-confirmation#order=synthetic&key=private-token')
  for value in ['Keynote','Workshop','2 × Shirt — Medium','1 × Shirt — Large','<strong>20261014</strong>','cid:apple','cid:google','Sign in to your dashboard']:self.assertIn(value,html)
  self.assertNotIn('Event: event',html);self.assertNotIn('SAMPLE CONFIRMATION',html)
  self.assertIn('https://registration.example/registrant-login?event=event',html)
  dashboard=html.split('Sign in to your dashboard')[0].rsplit('<a ',1)[-1];self.assertNotIn('private-token',dashboard)
