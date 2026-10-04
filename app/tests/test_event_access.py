import unittest,uuid
from datetime import datetime,timezone
from psycopg import sql
from tests.test_access import AccessTests
from access import AccessError
from database import Store
class EventAssignmentTests(AccessTests):
 def event(self,name='Assigned',store=None):
  store=store or self.store;eid=str(uuid.uuid4());now=datetime.now(timezone.utc).isoformat()
  return store.save(eid,dict(name=name,timezone='UTC',format='online',start='',end=''),now,False)
 def assigned(self,role,eids):
  address=role+'@example.test';uid=self.a.save_user(self.owner,dict(email=address,role=role,first_name='Test',last_name='Person',company_name='Demo company',products=['event-builder'],event_ids=eids));code=self.a.enrollment(self.owner,uid);self.a.activate(address,code,self.password);token=self.a.login(address,self.password)
  return uid,token,self.a.session(token)
 def test_roles_and_event_routes(self):
  yes=self.event();no=self.event('Other');flows=self.store.flows(yes['id'],{'name':'Media','kind':'media'},datetime.now(timezone.utc).isoformat());child=next(f['id'] for f in flows if f['id']!=yes['id'])
  for role in ('client','employee'):
   uid,raw,actor=self.assigned(role,[yes['id']]);self.assertEqual(actor['role'],role)
   self.assertEqual([e['id'] for e in self.request('/api/events',token=raw)[1]],[yes['id']])
   for tail in ('registration-page','membership','sessions','flows','welcome-page','event-footer','demographics','assets/'+str(uuid.uuid4())):
    self.assertEqual(self.request('/api/events/'+no['id']+'/'+tail,token=raw)[0],404,tail)
   self.assertEqual(self.request('/api/events/'+child+'/registration-page',token=raw)[0],200)
   for tail in ('pricing-preview','demographics-preview','membership/import','sessions/speaker'):
    self.assertEqual(self.request('/api/events/'+no['id']+'/'+tail,{},raw,actor['csrf'])[0],404,tail)
   self.assertEqual(self.request('/api/admin/users',token=raw)[0],403)
   self.a.save_user(self.owner,dict(email=role+'@example.test',role=role,status='active',products=['event-builder'],event_ids=[]));self.assertIsNone(self.a.session(raw));fresh=self.a.login(role+'@example.test',self.password)
   self.assertEqual(self.request('/api/events',token=fresh)[1],[]);self.assertEqual(self.request('/api/events/'+child+'/registration-page',token=fresh)[0],404)
 def test_admin_all_and_new_client_none(self):
  yes=self.event();self.event('Other');uid,raw,actor=self.assigned('admin',[])
  self.assertEqual(len(self.request('/api/events',token=raw)[1]),2);self.assertEqual(self.request('/api/events/'+yes['id']+'/registration-page',token=raw)[0],200)
  uid,raw,actor=self.user(['event-builder']);self.assertEqual(actor['role'],'client');self.assertEqual(self.request('/api/events',token=raw)[1],[])
 def test_profile_multiple_and_creator(self):
  es=[self.event('A'),self.event('B')];uid,raw,actor=self.assigned('employee',[e['id'] for e in es]);user=next(u for u in self.a.users(self.owner) if u['id']==uid)
  self.assertEqual(user['company_name'],'Demo company');self.assertEqual(len(user['event_ids']),2)
  status,body,_=self.request('/api/events',dict(name='Created',timezone='UTC',format='online'),raw,actor['csrf']);self.assertEqual(status,201);self.a.require_event(actor,body['id'])
 def test_cross_workspace(self):
  other=Store(schema='regfire_access_other_'+uuid.uuid4().hex);other.initialize()
  try:
   foreign=self.event('Foreign',other)
   with self.assertRaises(AccessError):self.assigned('client',[foreign['id']])
   self.assertEqual(self.request('/api/events/'+foreign['id']+'/registration-page',token=self.token)[0],404)
  finally:
   with other.connect() as c:c.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(other.schema)))
 def test_legacy_migration(self):
  es=[self.event('A'),self.event('B')];uid,raw,actor=self.user(['event-builder'])
  with self.store.connect() as c:
   c.execute(sql.SQL('ALTER TABLE {} DROP CONSTRAINT access_users_role_check').format(self.a.t('users')));c.execute(self.a.q("UPDATE {} SET role='user' WHERE id=%s",'users'),(uid,))
  self.store.initialize();self.assertEqual(self.a.session(raw)['role'],'client');self.assertEqual(self.a.event_ids(actor),{e['id'] for e in es})
  new=self.event('New');self.store.initialize();self.assertNotIn(new['id'],self.a.event_ids(actor))
if __name__=='__main__':unittest.main()
