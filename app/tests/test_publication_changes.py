import unittest
from publication_snapshot import change_details
class ConcreteChanges(unittest.TestCase):
 def test_added_removed_price_copy_and_secret_omission(self):
  a={'registration_pages':{'intro':'Old','regtypes':[{'id':'a','name':'Guest','price_minor':100},{'id':'b','name':'Old type'}]},'membership_settings':{'client_secret':'old'}}
  b={'registration_pages':{'intro':'New','regtypes':[{'id':'a','name':'Guest','price_minor':200},{'id':'c','name':'New type'}]},'membership_settings':{'client_secret':'new'}}
  r=change_details(a,b);self.assertTrue(any(x['before']==100 and x['after']==200 for x in r));self.assertTrue(any(x['action']=='Removed' and 'Old type' in x['path'] for x in r));self.assertTrue(any(x['action']=='Added' and 'New type' in x['path'] for x in r));self.assertFalse(any('secret' in str(x) for x in r))
 def test_session_status_and_reorder_are_not_hidden(self):
  a={'event_sessions':{'sessions':[{'id':'a','title':'Keynote','status':'active'},{'id':'b','title':'Workshop'}]}}
  b={'event_sessions':{'sessions':[{'id':'b','title':'Workshop'},{'id':'a','title':'Keynote','status':'cancelled'}]}}
  r=change_details(a,b);self.assertTrue(any(x['after']=='cancelled' for x in r));self.assertTrue(any(x['action']=='Reordered' for x in r))
