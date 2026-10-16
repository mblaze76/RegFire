# Draft publication and incomplete registration recovery

Saving setup is not publication. The publication panel compares the last published configuration with the current saved draft. Publishing requires both the current publication revision and the exact reviewed draft digest. Unsaved browser edits are never automatically saved or published by this panel.

The snapshot includes event details, registration fields/rates, demographics, sessions, additional options, shared event branding/footer, confirmation settings, membership policy and flow payment/tax preferences. Reads are scoped with a request-local ContextVar; the shared HTTP server/store is not replaced. Operational orders, inventory consumption, membership data and provider credentials/enablement stay live. Unpublishing closes new public registration access. Existing completed receipt routes retain their separate authorization checks. Migration captures legacy published configurations before later draft edits; runtime startup does not perform privileged migration.

## Incomplete registrations

Only a signed-in attendee account on a published flow can save an incomplete draft. Explicit field allowlists omit passwords, enrollment tokens, payment credentials and arbitrary metadata. Groups retain each attendee's permitted answers and selections; resume returns to the primary attendee and requires enrollment again. Prices, required answers, membership and inventory are revalidated by existing checkout logic.

Retention ends 30 calendar days after the published parent event's end, interpreted in its event timezone. Publishing a changed end date updates retained drafts' cutoffs. Missing event end dates disable incomplete-draft retention. Expired rows are inaccessible immediately; lazy cleanup runs on relevant operations and a retention-only background worker deletes expired/completed drafts at startup and hourly while the service runs. Offline periods defer physical deletion until startup. Completed order rows are never deleted by this worker.

The event-scoped organizer page **Send partial registration emails** lists drafts and previews the exact recipient/message. No automated email is sent. `REGFIRE_PARTIAL_EMAIL_LIVE=1` plus existing communications/confirmation readiness flags and approved provider configuration are required for an explicit send. These flags are not enabled by this change. Reminders are sent only to the owning attendee account address, never an arbitrary recipient. A row is durably marked submitting before a provider call. Timeouts remain unknown and cannot be retried through this UI; submitted reminders likewise cannot be resent. Operator reconciliation is required.

Resume links contain a random token in the URL fragment, never names/emails. Only its SHA-256 hash is retained. Tokens expire after at most seven days or the retention cutoff, are single-use, and require the same attendee account's login and CSRF protection. Possessing a link alone does not grant account access. A resumed draft must be reviewed; it cannot mark an order paid or reserve inventory.

## Client intake

The XLSX importer supports event details, categories/base prices, sessions, simple additional options, shared fonts/colors and confirmation heading/message. It validates a bounded values-only workbook before offering an owner-bound, 30-minute review. Apply creates one new unpublished draft transactionally, is idempotent, and does not update an existing event. Images, option variants, dated pricing, demographic questions and provider settings remain setup tasks. Native Google Sheet delivery requires the designated RegFire Drive connection.

## Release boundaries

Local tests and synthetic browser checks do not prove cloud migration, deployment, provider integration or actual email delivery. No live event configuration, passwords or provider enablement should be changed by release tests.
