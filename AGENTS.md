# RegFire project workflow

The user has authorized ongoing GitHub synchronization after each completed, verified change batch.

- Repository: https://github.com/mblaze76/RegFire (public).
- Application source: `outputs/regfire` maps to `app/`.
- Corporate source: `/Users/mikeblaze/Documents/ChatGPT/RegFire` maps to `corporate-site/`.
- Review, test and commit finished changes, then push/update GitHub and verify the remote commit. Preserve remote changes and local work. Prefer batched Git operations; avoid one approval per source file when a supported batched update is available.
- Never upload credentials, `.local/`, runtime databases, event/customer/member data, uploads, backups, virtual environments, caches or unrelated files. Keep synthetic test fixtures and required branding/media assets.
- Do not describe work as synchronized if authentication, approval or push fails. Report pending sync clearly.
- Corporate site is published to Netlify. Deployment directory is `corporate-site/dist` only. Verify the resulting public site after website changes. GitHub continuous deployment is not confirmed until actually configured and verified.
- Domain intent: `www.regfire.events`; preserve mail DNS and never buy a domain or paid plan without a separate request.
- This authorization is for completed work, not periodic background automation or blind syncing of unfinished changes.
