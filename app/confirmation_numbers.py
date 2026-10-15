"""Stable public identifiers; never a substitute for event or receipt authorization."""
import re
from psycopg import sql

def number(store, order_id):
 with store.connect() as c:
  row=c.execute(sql.SQL('SELECT confirmation_number FROM {} WHERE id=%s').format(sql.Identifier(store.schema,'registration_orders')),(order_id,)).fetchone()
 if not row:raise ValueError('Registration not found.')
 return str(row[0])

def lookup(store, flow, reference):
 """Caller must authorize access to flow before invoking this organizer-only lookup."""
 if re.fullmatch(r'[0-9]{8}',reference):column='confirmation_number';value=int(reference)
 elif re.fullmatch(r'[a-f0-9-]{36}',reference):
  import uuid
  try:value=str(uuid.UUID(reference))
  except ValueError:return None
  column='id'
 else:return None
 with store.connect() as c:
  row=c.execute(sql.SQL("SELECT body FROM {} WHERE flow_id=%s AND {}=%s AND status IN ('paid','confirmed_free')").format(sql.Identifier(store.schema,'registration_orders'),sql.Identifier(column)),(flow,value)).fetchone()
 return row[0] if row else None
