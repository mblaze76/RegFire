import datetime,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deploy'))
import confirmation_test_worker as worker
from test_confirmation_worker import ConfirmationWorkerTests
class ScopedTests(ConfirmationWorkerTests):
 def policy(self):return worker.scope(self.store,'blaze@regfire.events',(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=2)).isoformat())
 def recipient(self,ident,address):
  from psycopg import sql
  with self.store.connect() as c:c.execute(sql.SQL('UPDATE {} SET recipient=%s WHERE order_id=%s').format(sql.Identifier(self.schema,'confirmation_delivery')),(address,ident))
 def test_only_new_designated_recipient(self):
  old=self.order();self.recipient(old['id'],'blaze@regfire.events');policy=self.policy();new=self.order();self.recipient(new['id'],'blaze@regfire.events');other=self.order()
  with patch('confirmation_delivery.dispatch') as dispatch:
   r=worker.run_once(self.store,self.settings(),policy);self.assertEqual(r['submitted'],1);self.assertEqual(dispatch.call_args.args[2],new['id'])
 def test_expired_does_not_dispatch(self):
  policy=self.policy();new=self.order();self.recipient(new['id'],'blaze@regfire.events')
  with patch('confirmation_delivery.dispatch') as dispatch:
   self.assertEqual(worker.run_once(self.store,self.settings(),policy,now=policy['expires'])['state'],'expired');dispatch.assert_not_called()
 def test_wrong_recipient_and_long_window_rejected(self):
  for address,hours in [('other@example.test',2),('blaze@regfire.events',25)]:
   with self.assertRaises(ValueError):worker.scope(self.store,address,(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=hours)).isoformat())
