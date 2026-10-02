# Organizer registration-page builder

Open a saved event and choose **Registration page**. A new event must be saved first so its page has a stable event ID. This is an organizer authoring workspace, not an event dashboard or live attendee registration service.

## Build a page

1. Set the page title and optional introduction.
2. Add and name the event's **RegTypes**. Set their displayed prices and the event currency. Use the up/down buttons to order them.
3. Customize the fields: label, type, required status, choices and visibility. Add, reorder or remove fields as needed.
4. In **Attendee preview**, select each RegType to inspect its price and questions. On smaller screens, the **Preview** button jumps to this area.
5. Click **Save page draft**. The page is stored in PostgreSQL for this event and can be reopened after reload or app restart.

Page drafts begin with Full name and Email required, Phone and Address optional, and one editable RegType named Attendee priced at zero. These are starting points, not fixed categories or a required collection policy. The starter is not written to the database until you save it.

The event-details draft and registration-page draft save separately. Editing an event name does not rewrite a saved registration page's title. Switching views/events with unsaved changes asks before discarding them. Preview answers never save. URL fragments remember the selected event/view for a reload; they are local navigation, not published registration links.

## Fields and contact information

Supported types: short text, email, phone, long text, dropdown, single choice, checkbox and structured address. Labels and choice text are organizer-editable. Dropdown and single-choice fields need 2–30 distinct, nonblank choices.

The address block contains address line 1, optional line 2, city, state/province/region, postal code and country. A block's required flag applies to all components except line 2, which is always optional. Use an optional block where country-specific addresses do not require every component; per-component required settings and country-specific validation are not implemented.

Phone uses `type=tel` without a domestic-only pattern. International prefixes, spaces and extensions are accepted. Phone-number verification, normalization and dial-code lookup are not implemented. Country is free text, and postal code is text to preserve letters and leading zeros.

## RegTypes, prices and visible questions

Each RegType has a stable ID, editable name and integer `price_minor`. Reordering or renaming it does not change that ID. RegTypes are defined within the event's page draft; no shared global categories are imposed.

Choose **All RegTypes** or **Selected RegTypes** for each field. Selected visibility needs at least one current RegType. The preview renders only fields applicable to its selected type, so hidden required fields cannot block a preview check. Switching RegType or editing the page rebuilds the preview and clears its temporary answers.

Removing a RegType referenced by any field is blocked. First change those fields to all types or to other types. This avoids silently exposing restricted questions or losing a condition. The server also rejects stale or duplicate references without changing the saved draft. Field and RegType removals require confirmation; at least one of each must remain. There is no saved-draft revision history or undo after saving.

Supported currencies: USD, EUR, GBP, CAD and AUD (two decimal places), and JPY (whole yen). USD is the editable starter default. Prices are nonnegative; the maximum is 99,999,999 minor units: 999,999.99 for two-decimal currencies or 99,999,999 JPY. Decimal input is parsed into integer minor units without binary floating-point rounding. For example, USD 125.50 is stored as `12550`.

Changing currency asks for confirmation and keeps the entered numeric amounts; it performs no exchange-rate conversion. A fractional amount is rejected if switched to JPY. Review all prices and save only when they are correct. Supported currency choices are deliberately limited; there is no exchange-rate service or inferred conversion.

## Preview boundaries

**Check preview** uses the browser's required/email checks for the currently visible inputs. A successful check shows a preview-only message. It does not create an attendee, charge money, send email, submit a registration, reserve capacity or publish anything. No backend attendee-submission endpoint or response table exists.

RegTypes currently control only displayed registration price and registration-question visibility. They do not grant access to event areas, change badge layouts, control scanning, impose capacity, calculate taxes/fees/discounts or process payments. Those behaviors and cloud migration remain deferred.

## Named rate periods and expiry

Each RegType now has an editable **Default price** and up to 20 named dated rates, such as Early bird, Standard or Late. Each rate has its own exact minor-unit price, stable ID, and optional start/end in the event's timezone. At least one boundary is required; use the default for an undated price.

Start is inclusive; end is exclusive. An Early bird ending October 2 at 09:00 is no longer active at 09:00. A Standard rate may start at that same minute without overlap. Blank start means no lower boundary; blank end means no expiry. Overlapping, reversed or zero-length windows are rejected, including overlaps involving open boundaries. Names must be unique within a RegType. Ordering the rate cards does not determine priority; nonoverlapping times do.

A dated period takes priority over the default. **Use default rate outside dated periods** is enabled for existing single prices, preserving their behavior. That default does not expire while enabled. Disable it if registration pricing should be unavailable before the first period, during gaps, or after the last period. The preview explicitly says **No active rate** and disables its check button when no price applies. It never silently reuses an expired dated price.

Use **Preview pricing at** to test a local date/time in the event timezone. Blank means current time; **Use current time** clears the test date. Pricing is evaluated by the server, not the browser's timezone. Current-time previews refresh at minute boundaries while visible and on returning to the tab; this is a local preview, not a payment quote or booking system.

All boundaries have minute precision. Nonexistent spring-forward times are rejected. In the repeated fall-back hour, the first occurrence is used, consistent with event-time handling. Changing an event timezone reinterprets the saved local rate times; the server revalidates them and rejects a change that creates invalid local times. Review periods after changing timezone. Currency changes keep numeric amounts for the default and every dated rate, with no exchange-rate conversion.

## Drag-and-drop field ordering

Drag the dotted handle beside a field's number. A warm line shows whether it will be placed before or after another field. Release to commit the new order; cancellation leaves it unchanged. The whole field definition moves—its ID, type, label, choices, required setting and visibility rules stay together. The preview updates immediately; **Save page draft** persists the order.

Handles support pointer/touch events and edge scrolling. Up/down controls remain available for keyboard use and as a touch fallback. Actual desktop dragging was verified; physical-device touch dragging has not been tested. Dragging starts only from the handle so selecting text or editing a field does not move it.

## Client/show branding

Use **Show branding** to upload a show logo and a background image for this event's registration page. Uploading a replacement creates a new asset and selects it in the editor; **Save page draft** commits the selection. Remove controls clear the draft selection; removing the logo returns to the Regfire preview logo. The approved organizer-shell logo and colors remain unchanged.

Supported inputs: static PNG, JPEG and WebP, up to 8 MB, 6000 pixels per side and 16 megapixels. SVG, animated and invalid images are rejected based on actual content, not filename or claimed MIME type. Uploaded images are orientation-corrected, reduced to fit within 2560×2560 without distortion, stripped of metadata and normalized to PNG with a maximum normalized size of 16 MB. The original input filename is never used for storage.

**Background fade** ranges from 0% (fully visible image) to 100% (hidden image), with 80% as the starting setting. It updates the preview immediately. Only the background layer fades; the registration content stays opaque on a white card. The background covers its responsive surrounding surface, and the logo uses contained sizing without stretching.

Uploads are event-specific. The server rejects image references from other events or the wrong asset kind. Images and saved appearance survive restart. Preview answers still do not save. Removed/replaced/unselected assets are retained locally to protect saved drafts and cancelled changes; there is no automatic disk cleanup or permanent-delete UI. They can consume storage until deliberate maintenance. See the operations guide: current backups must include PostgreSQL **and** the `uploads/` directory.

## Separate preview and related setup

Use **Open live preview ↗** for a separate attendee window that reflects unsaved edits; see LIVE_PREVIEW.md. Demographics is a separate organizer-only question/branching editor (DEMOGRAPHICS.md). Membership has its own settings and check preview (MEMBERSHIP.md). Address blocks support optional provider-ready suggestions while preserving manual entry and line 2 (ADDRESS_LOOKUP.md).
