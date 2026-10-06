# Password recovery

Clients, employees, and administrators with active accounts and an existing password can use **Forgot password?** on `/login`. The protected initial owner is excluded. Administrators retain private setup/reset codes, and only the owner can reset an administrator through that control. Administrators cannot reset themselves through administration.

Email recovery requires an existing authorized SMTP service. No provider account, paid plan, DNS change, or customer email is created by this feature. Connected Gmail access is not an application SMTP credential.

Create `.local/recovery-mail.json` (excluded from Git) with these string settings, or set them in the server environment. Environment settings take precedence. Keep the file readable only by your operating-system account (`chmod 600 .local/recovery-mail.json`). Never commit it or paste its password into chat.

```json
{
  "REGFIRE_SMTP_HOST": "smtp.your-provider.example",
  "REGFIRE_SMTP_PORT": "587",
  "REGFIRE_SMTP_SECURITY": "starttls",
  "REGFIRE_SMTP_USERNAME": "your-provider-smtp-user",
  "REGFIRE_SMTP_PASSWORD": "your-provider-smtp-password",
  "REGFIRE_SMTP_FROM": "your-verified-sender@example.com",
  "REGFIRE_PUBLIC_URL": "https://your-actual-builder-host.example"
}
```

The sender must be authorized/verified by the provider. Use provider-supplied SMTP credentials, not an ordinary mailbox password. TLS is mandatory: `ssl` (default port 465) or `starttls` (587). A trusted relay may omit both username and password. The public URL must be the actual reachable **builder** origin, not the corporate landing page. HTTP is accepted only for loopback development; a loopback reset link works only on that same computer.

Restart the builder after configuration. Its normal startup applies the additive migration. Administration shows whether configuration is complete; this is not proof of delivery. The existing local server is not a hardened public deployment. Production hosting still needs a separate HTTPS/host/origin and Secure-cookie integration; the existing server only accepts local hosts and HTTP origins, so an HTTPS URL here alone does not enable a public deployment; do not publish the builder merely to enable recovery.

For a delivery check, explicitly authorize one email to a controlled test mailbox and use an isolated test account. No real customer account or password should be used. Configuration alone does not send mail. Automated tests inject a fake sender and create disposable database schemas.

## Security behavior

- Same generic request response for missing, suspended, owner, and eligible accounts; delivery happens in a bounded background queue.
- 32-byte random tokens, stored only as SHA-256 hashes, expire in 30 minutes. Links use a URL fragment removed by the login page; it is not sent in HTTP requests.
- A successful reset revokes all existing sessions, reset links, and manual enrollment codes. It does not automatically sign in or change roles, grants, or suspension state.
- Requesting a link never changes a password or revokes a session. Redemption verifies mailbox possession; manual administrator codes do not independently verify email.
- Per-address requests: 3/hour. Per source IP: 20 requests or redemption attempts/15 minutes. Global mail requests: 200/hour. Counters persist across restarts and do not consume the sign-in rate limit. Source IP is the socket peer; forwarded IP headers are not trusted. Deployments behind a proxy share that proxy's limit unless a trusted-proxy design is added.
- Account access changes and administrator code issuance invalidate reset links. Audit entries contain account IDs and actions, never tokens, passwords, or SMTP errors.
- Queued mail is intentionally in memory; a restart may discard pending requests. Ask for another link after restarting. SMTP acceptance is audited as submitted, not delivered.

Run: `.venv/bin/python -m unittest discover -s tests -p 'test_password_recovery.py' -v`
