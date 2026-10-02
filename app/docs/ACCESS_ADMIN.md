# Local sign-in and access administration

RegFire now includes `/login`, `/products`, and `/admin`. These are local-only routes, not public client URLs. The server still binds only to loopback and rejects other Host headers. Do not link a public corporate site to localhost or expose this server through a proxy.

## Initial owner

The private `.local/owner-policy.json` reserves initial ownership for **blaze@regfire.events**. There is no default password and no public self-registration. Start the updated server, then run `.venv/bin/python owner_setup.py` from the app directory. It opens a private, one-use setup link in the default browser without printing credentials. The owner enters and confirms a password in the setup page. The URL fragment is immediately removed from browser history by the page; it is never sent to the server in a URL or logged. The random setup code is stored owner-only in `.local/owner-setup.json`, excluded from Git, and deleted after successful setup. The owner email is read from the private policy, not accepted from a submitted account form. Subsequent setup requests fail.

A Terminal-only alternative is `.venv/bin/python bootstrap_owner.py`; it reserves the same email and prompts with getpass. Owner setup itself does not prove mailbox ownership. Do not share the private setup code.

The owner is shown as Super admin. Only the owner can create or change administrator accounts. The owner cannot be suspended, demoted, or edited through the administration API, and ordinary administrators cannot elevate themselves. A local database operator remains trusted.

## Account lifecycle

Administrators assign an email, role, account status, and any number of registered products. New accounts are Assigned until a password is established. Generating an enrollment code does not send email. Codes expire after 24 hours, are stored only as hashes, are single-use, and are replaced when regenerated. An administrator must privately provide a code only after independently confirming who should receive it. Enrollment also supports password reset for non-owner accounts. Email verification remains explicitly false; no mailbox verification or external identity provider is implemented.

Suspension blocks sign-in. Saving user access immediately revokes all that user's sessions and outstanding enrollment codes. Every request rechecks current account state, role, product grants, and product enabled state on the server. Product access is not a UI-only restriction. Session expiry, sign-out, and administrative revocation invalidate API access.

## Products and shared data

RegFire Nexus is the sole connected product. The registry allows future product IDs, names, and enabled state, plus advance assignment of grants. Future products have no launch link until code integrates their routes and server-side authorization. Registering a name does not create a functioning product. RegFire Nexus access grants access to **all existing events in this shared workspace**. There is no tenant or per-client event isolation. Do not enroll unrelated external clients until isolation and public HTTPS hosting are designed and verified.

## Security and operations

Passwords use salted scrypt (N=32768, r=8, p=3), with a 12–256 character input range. Sessions use random 256-bit tokens, hash-only token storage, an eight-hour expiry, and HttpOnly / SameSite=Strict cookies. Cookie names include the server port to avoid cross-session collisions among local test instances. Secure cookies are not used for this HTTP loopback-only edition; production HTTPS, secure cookies, trusted origins, MFA/recovery, deployment secret management, and external identity verification remain launch work.

State-changing requests require exact same-origin Origin plus a per-session CSRF token; unauthenticated login/setup/enrollment still require same-origin JSON. Login and enrollment attempts are bounded in memory per server process (20 per 15 minutes); this is not a distributed production rate limiter. No credentials or enrollment codes are written to request logs. Audit records include owner creation, sign-ins, user/product access changes, and enrollment actions, without secrets. There is no email-sending integration.

Migration 005 is additive; existing events, registration pages, demographic questions, membership settings and assets are unchanged. Back up the database normally before deployment. The existing local process must be restarted to load authorization; editing files alone does not secure an already-running older server. Before restarting, ensure draft edits are saved. All product APIs—including assets, address lookup, membership and preview endpoints—then require authentication and the event-builder grant.

## Validation

The full test suite passed: 63 tests, including 10 new access tests and authenticated regressions for existing events, assets, membership, demographics and address adapters. Tests use disposable PostgreSQL schemas and generated test-only credentials. UI checks use a separate disposable schema, never the real owner or event data.

Design references: [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html), [CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

Follow-up private-bootstrap validation passed all 11 access checks, including rejection of an invalid setup code, pinning to the configured owner email even when another email is submitted, deletion of the used code, and rejection of repeat setup. Chrome verified sign-in, an assigned user's product grant, protected-owner display, and sign-out using disposable QA accounts; that test server and schema were removed afterward.
