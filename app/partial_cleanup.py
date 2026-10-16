"""Retention-only maintenance. No provider access or email delivery."""
import logging,threading
from partial_registration import cleanup

def start(store,interval=3600):
 stop=threading.Event()
 def run():
  while not stop.is_set():
   try:cleanup(store)
   except Exception:logging.getLogger(__name__).warning('Incomplete-registration retention cleanup failed; expired links remain denied. Will retry.')
   stop.wait(interval)
 threading.Thread(target=run,name='partial-retention',daemon=True).start()
 return stop

if __name__=='__main__':
 from database import Store
 print('Expired/completed incomplete drafts removed:',cleanup(Store()))
