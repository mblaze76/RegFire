# Registration confirmations

Confirmation setup follows Payment in each registration flow. The saved layout, message, section visibility, sponsor assets and QR placement are flow-specific. Unsaved edits update both previews without saving. Drag handles have arrow-button and QR-select alternatives. PDF exports use the same section order and QR placement, white paper and print fonts. Normal sample output is one page; long orders paginate.

Actual confirmations and receipt downloads require the signed-in owner of a saved paid or confirmed-free order. Amounts come from the stored server quote. Sandbox and sample output is explicitly labeled and cannot issue wallet passes. QR content is JSON containing only event_id and confirmation_id.

## Private provider prerequisites

Superadmin tools > Communications reuses the existing Bird or SendGrid connection. Configure a verified sender, optional reply-to and public HTTPS app origin. Credentials remain masked and server-side. Completed nonsandbox orders queue one confirmation each. Queuing never sends email. An explicitly operated worker must call confirmation_delivery.dispatch; no background sender or automatic startup delivery is installed. Both REGFIRE_CONFIRMATION_EMAIL_LIVE=1 and REGFIRE_COMMUNICATIONS_LIVE=1 are required. Unknown submissions are never automatically retried. Provider acceptance is not proof of inbox delivery.

Superadmin tools > Wallet passes stores private settings in .local/wallet.json with owner-only permissions. Apple requires an existing Pass Type ID, team ID, matching signing certificate/private key and WWDR certificate. Google requires an existing issuer, approved generic class and authorized service-account JSON. Local validation and synthetic signing tests do not establish provider approval or device acceptance. Live device testing remains required.

Apple badge artwork is an optional visual prerequisite: supply the officially licensed asset. The UI currently uses a neutral text button and does not accept Apple's license automatically. Google Wallet artwork is unmodified en-US artwork from https://developers.google.com/static/wallet/download-assets/add-to-wallet-svg.zip and add-to-wallet-png.zip, referenced by https://developers.google.com/wallet/generic/resources/brand-guidelines (retrieved 2026-10-11).

No email, paid transaction, wallet account, production credential or provider purchase was made during implementation.

## Verification

260 regression tests passed. Confirmation coverage includes flow isolation, save/restart, stale revision, unsaved preview, foreign asset rejection, pending-order and cross-actor denial, exact QR keys, PDF creation/pagination, owner-only provider settings, duplicate-safe outbox and unknown-submission protection. Synthetic RSA tests verify Google JWT claims/signature and Apple archive contents/manifest.

Browser checks in an isolated synthetic event cover three-logo upload, individual controls, section and QR drag, keyboard ordering, save/reload, live detached preview, 390px mobile layout without horizontal overflow and completed free-order rendering. Standard PDF visually inspected and QR decoded. Live paid-provider, real email delivery and physical-device wallet acceptance are not verified.
