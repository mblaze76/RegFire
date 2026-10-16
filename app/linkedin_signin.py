"""Attendee-only identity binding. Never grants organizer access or links by email alone."""
import secrets,uuid
from psycopg import sql
import attendee_accounts as aa
from access import email
ISSUER='https://www.linkedin.com'

def link_proof(h):
 token=aa.digest(aa.raw_cookie(h))
 with h.server.store.connect() as c:
  row=c.execute(sql.SQL("SELECT account_id FROM {} WHERE token_hash=%s AND expires>now() AND auth_method='password' AND authenticated_at>now()-interval '15 minutes'").format(aa.table(h.server.store,'attendee_sessions')),(token,)).fetchone()
 return dict(session_hash=token,account_id=str(row[0])) if row else None

def complete(store,flow,claims,proof=None):
 from publication import enabled
 if not enabled(store,flow):raise ValueError('Registration is unavailable.')
 subject=claims.get('subject');address=email(claims.get('email'))
 if claims.get('email_verified') is not True or not isinstance(subject,str) or not 1<=len(subject)<=255:raise ValueError('LinkedIn must provide a verified email and account identity.')
 session=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24);enrollment=secrets.token_urlsafe(32)
 with store.connect() as c:
  linked=c.execute(sql.SQL('SELECT a.id,a.email,a.password_hash FROM {} i JOIN {} a ON a.id=i.account_id WHERE i.issuer=%s AND i.subject=%s').format(aa.table(store,'attendee_social_identities'),aa.table(store,'attendee_accounts')),(ISSUER,subject)).fetchone()
  if linked:account,address,encoded=linked
  else:
   existing=c.execute(sql.SQL('SELECT id,password_hash FROM {} WHERE email=%s FOR UPDATE').format(aa.table(store,'attendee_accounts')),(address,)).fetchone()
   if existing:
    verified=None
    if proof:verified=c.execute(sql.SQL("SELECT account_id FROM {} WHERE token_hash=%s AND account_id=%s AND expires>now() AND auth_method='password' AND authenticated_at>now()-interval '15 minutes'").format(aa.table(store,'attendee_sessions')),(proof.get('session_hash'),existing[0])).fetchone()
    if not verified:raise ValueError('Sign in to your existing attendee account with its password, then choose LinkedIn again to link it.')
    account,encoded=existing
   else:
    account=str(uuid.uuid4());encoded=aa.password_hash(secrets.token_urlsafe(48))
    c.execute(sql.SQL('INSERT INTO {}(id,email,password_hash) VALUES(%s,%s,%s)').format(aa.table(store,'attendee_accounts')),(account,address,encoded))
   c.execute(sql.SQL('INSERT INTO {}(issuer,subject,account_id) VALUES(%s,%s,%s)').format(aa.table(store,'attendee_social_identities')),(ISSUER,subject,account))
  c.execute(sql.SQL("INSERT INTO {}(token_hash,account_id,csrf,auth_method,authenticated_at) VALUES(%s,%s,%s,'linkedin',now())").format(aa.table(store,'attendee_sessions')),(aa.digest(session),account,csrf))
  c.execute(sql.SQL('INSERT INTO {}(token_hash,actor_id,flow_id,email,password_hash,account_id) VALUES(%s,%s,%s,%s,%s,%s)').format(aa.table(store,'attendee_enrollments')),(aa.digest(enrollment),account,flow,address,encoded,account))
 return dict(session=session,enrollment_token=enrollment,email=address)
