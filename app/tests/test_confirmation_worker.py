import os, unittest, uuid
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from psycopg import sql
import test_checkout as tc
import confirmation_worker as worker
from communications_settings import Settings
class ConfirmationWorkerTests(unittest.TestCase):
 setUp=tc.CheckoutStorage.setUp;tearDown=tc.CheckoutStorage.tearDown;start=tc.CheckoutStorage.start;stop=tc.CheckoutStorage.stop;request=tc.CheckoutStorage.request;auth_headers=tc.CheckoutStorage.auth_headers;setup_order=tc.CheckoutStorage.setup_order
 def order(self):
  flow,_,data=self.setup_order(0);o=self.request('/api/events/'+flow+'/checkout/save',data,'POST');self.request('/api/checkout/'+o['id']+'/start',{},'POST');return o
 def settings(self):
  s=Settings(Path(self.upload_tmp.name)/'worker-email.json');c=s.public();c.update(public_url='https://regfire.example');c['email'].update(provider='sendgrid',sender='events@regfire.example',secret_action='replace',secret='synthetic_test_secret');s.save(c);return s
 def state(self,ident):
  with self.store.connect() as c:return c.execute(sql.SQL('SELECT status FROM {} WHERE order_id=%s').format(sql.Identifier(self.schema,'confirmation_delivery')),(ident,)).fetchone()[0]
 def test_competing_workers_send_once(self):
  o=self.order();s=self.settings()
  with patch.dict(os.environ,REGFIRE_STAGING='0',REGFIRE_CONFIRMATION_EMAIL_LIVE='1',REGFIRE_COMMUNICATIONS_LIVE='1'),patch('confirmation_delivery.adapter_for') as p:
   p.return_value.submit.return_value={'status':'submitted','provider_id':'fake'}
   with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:worker.run_once(self.store,s),range(2)))
   worker.run_once(self.store,s);self.assertEqual(p.return_value.submit.call_count,1);self.assertEqual(self.state(o['id']),'submitted')
 def test_timeout_not_retried(self):
  o=self.order();s=self.settings()
  with patch.dict(os.environ,REGFIRE_STAGING='0',REGFIRE_CONFIRMATION_EMAIL_LIVE='1',REGFIRE_COMMUNICATIONS_LIVE='1'),patch('confirmation_delivery.adapter_for') as p:
   p.return_value.submit.side_effect=TimeoutError();self.assertEqual(worker.run_once(self.store,s)['failed'],1);worker.run_once(self.store,s);self.assertEqual(p.return_value.submit.call_count,1);self.assertEqual(self.state(o['id']),'unknown')
 def test_render_failure_blocks(self):
  o=self.order();s=self.settings()
  with patch.dict(os.environ,REGFIRE_STAGING='0',REGFIRE_CONFIRMATION_EMAIL_LIVE='1',REGFIRE_COMMUNICATIONS_LIVE='1'),patch('confirmation_email.prepare',side_effect=ValueError()),patch('confirmation_delivery.adapter_for') as p:
   worker.run_once(self.store,s);p.assert_not_called();self.assertEqual(self.state(o['id']),'blocked')
 def test_staging_never_sends(self):
  self.order();s=self.settings()
  with patch.dict(os.environ,REGFIRE_STAGING='1',REGFIRE_CONFIRMATION_EMAIL_LIVE='1',REGFIRE_COMMUNICATIONS_LIVE='1'),patch('confirmation_delivery.adapter_for') as p:
   self.assertEqual(worker.run_once(self.store,s)['state'],'disabled');self.assertIsNone(worker.start(self.server));p.assert_not_called()
 def test_colleague_has_own_confirmation_without_primary_login_link(self):
  o=self.order();s=self.settings()
  with self.store.connect() as c:c.execute(sql.SQL("UPDATE {} SET body=jsonb_set(body,'{{group_parent_id}}',to_jsonb(%s::text)) WHERE id=%s").format(sql.Identifier(self.schema,'registration_orders')),(str(uuid.uuid4()),o['id']))
  with patch.dict(os.environ,REGFIRE_STAGING='0',REGFIRE_CONFIRMATION_EMAIL_LIVE='1',REGFIRE_COMMUNICATIONS_LIVE='1'),patch('confirmation_delivery.adapter_for') as p:
   p.return_value.submit.return_value={'status':'submitted','provider_id':'fake'};worker.run_once(self.store,s);args=p.return_value.submit.call_args;self.assertIn(o['id'],args.args[2]);self.assertNotIn('/confirmation#',args.args[2]);self.assertNotIn('/confirmation#',args.kwargs['html'])
 def test_disabled_does_not_load_settings(self):
  with patch.dict(os.environ,REGFIRE_CONFIRMATION_EMAIL_LIVE='0'),patch('communications.settings_for') as s:self.assertIsNone(worker.start(self.server));s.assert_not_called()
 def test_group_completion_queues_individual_recipients_and_ids(self):
  flow,_,data=self.setup_order(0)
  second=data|{'contacts':data['contacts']|{'email':'colleague@example.test','first-name':'Colleague'}}
  root=self.request('/api/events/'+flow+'/checkout/group-save',{'request_key':str(uuid.uuid4()),'members':[data,second]},'POST')
  self.request('/api/checkout/'+root['id']+'/start',{},'POST')
  self.request('/api/checkout/'+root['id']+'/start',{},'POST')
  with self.store.connect() as c:rows=c.execute(sql.SQL('SELECT order_id,recipient FROM {} ORDER BY recipient').format(sql.Identifier(self.schema,'confirmation_delivery'))).fetchall()
  self.assertEqual(len(rows),2);self.assertEqual({str(r[0]) for r in rows},set(root['group_order_ids']));self.assertEqual({r[1] for r in rows},{'synthetic@example.test','colleague@example.test'})
