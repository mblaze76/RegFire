#!/usr/bin/env python3
"""Run privately in Terminal. Passwords are never passed in arguments or printed."""
import getpass
from database import Store
from access import Access,AccessError

def main():
 store=Store();store.initialize();a=Access(store)
 if a.configured():raise SystemExit('An owner already exists. No changes made.')
 print('Create the initial LOCAL RegFire owner. This does not verify an email inbox or enable public client access.')
 from owner_setup import owner_email
 address=owner_email();print('Reserved owner: '+address);password=getpass.getpass('Password (12–256 characters): ')
 if password!=getpass.getpass('Confirm password: '):raise SystemExit('Passwords did not match. No account created.')
 try:a.bootstrap(address,password)
 except AccessError as e:raise SystemExit(str(e))
 print('Owner created. Restart RegFire, then open http://127.0.0.1:8765/login.')
if __name__=='__main__':main()
