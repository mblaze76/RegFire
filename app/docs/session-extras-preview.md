# Sessions, extra options, and badge previews

Sessions now supports optional capacity (blank is unlimited, zero is sold out) and a flow-scoped Show canceled sessions setting. Canceled sessions are marked in text and light red and cannot be selected. Agenda day chips use actual session dates, and filters combine with the selected day. Zero-price sessions display Included. Selecting a session in the preview does not reserve a seat, collect payment, or reduce capacity.

Extra options follows Sessions in the setup sequence. Each flow has independent physical items and services/experiences, prices, optional inventory, variants/sizes with their own inventory, and single/multiple quantity settings. A physical-item tax flag records organizer intent; the app does not invent a tax rate or include tax in item prices. The final checkout/order summary is not implemented. Preview item subtotals remain separate from registration fees. Saved-preview selections are validated against current saved inventory, but they do not reserve or buy anything.

The sample badge in attendee-details previews updates from first/last name, company or organization, city/state, and registration category. Empty values use placeholders. Values are inserted as text and retained through category and organizer preview updates within the same flow. Preview attendee values are not broadcast to other windows or saved as registrations. The badge is a visual sample, not a printing system.

Validation for this batch: 236 Python regression tests passed, including flow isolation, revision conflict handling, restart persistence, inventory/variant validation and quote calculations. Save-and-next JavaScript tests cover each successful next step and failure staying on the current page. Browser checks cover desktop and true 375-pixel content width, canceled/sold-out controls, Included and day filtering, saved item subtotals, speaker image loading, and live badge typing/category changes/long values. Google Vision, LinkedIn, email, SMS, checkout, and actual reservations were not live-provider tested.

## Speaker lightbox and superadmin shortcuts

Hover over a session row or focus its title to preview session details and every assigned speaker profile. Click/tap the title or speaker name to pin the lightbox. Close, Escape, or a click on the dimmed backdrop dismisses the pinned lightbox and returns keyboard focus. Photos, roles, organizations, and biographies use the saved speaker profiles. Missing biographies and speakers receive explicit placeholders. The same renderer is used in embedded, saved, and separate live previews.

Superadmin tools are available in the event sidebar and on the Products and Administration pages. Shortcuts lead to Bird setup, people/event access, password recovery, product access, the access audit, client settings, and products. Existing server permissions still apply; no new access is granted by these links.

Lightbox DOM regression test: install `linkedom@0.18.13` in a temporary test directory and set `NODE_PATH` to that directory's `node_modules`, then run `node tests/browser/test_session_lightbox.cjs`. It checks delayed hover, touch behavior, safe profile text, stale-hover cleanup, modal pinning, Escape/focus return, and missing-speaker fallback. The dependency is test-only.
