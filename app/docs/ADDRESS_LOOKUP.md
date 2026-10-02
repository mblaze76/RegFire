# Google address suggestions

Google Places (New) now supports autocomplete and selected-address field population. It is **not** Google Address Validation and does not certify postal deliverability. The existing Geoapify and synthetic providers remain supported.

The local server reads `.local/google-maps-key` (owner-only permissions, excluded from Git), or `REGFIRE_GOOGLE_MAPS_API_KEY`. On startup it selects Google when a private key is present unless `REGFIRE_ADDRESS_PROVIDER` explicitly selects another provider. Credentials never appear in browser responses. Restart the app after configuration changes.

Only Places API (New) is needed. Autocomplete uses a per-field session token; selecting a result requests only `addressComponents,formattedAddress`. Suite/address line 2 is preserved. Google attribution is displayed with predictions. Requests use a fixed Google HTTPS endpoint, validated public-IP pinning, certificate verification with system plus certifi trust, and bounded response sizes/timeouts. The key is carried in an HTTPS header. Provider failures retain manual entry.

Verified in Chrome on port 8766 using Google's public 1600 Amphitheatre Parkway address: suggestions appeared; selection populated Mountain View, California, 94043, United States while retaining a test Suite 42. No event or attendee record was saved. The older process on 8765 still needs a restart; process termination was denied by the environment.

References: [Autocomplete](https://developers.google.com/maps/documentation/places/web-service/place-autocomplete), [Place Details](https://developers.google.com/maps/documentation/places/web-service/place-details).

## Previous Geoapify setup


The provider-ready adapter uses [Geoapify Address Autocomplete](https://apidocs.geoapify.com/docs/geocoding/address-autocomplete/), whose documented response includes street, city, state, postcode and country. A provider API key is required. No key was configured, no provider account was created, and no paid or live address API call was made during implementation.

To activate real lookup, choose Geoapify and configure **both** server environment variables before restarting:

- `REGFIRE_ADDRESS_PROVIDER=geoapify`
- `REGFIRE_GEOAPIFY_API_KEY` with a key from your own Geoapify project, entered privately in the server environment, not in chat or source code.

Review your provider plan/quota before enabling it. This app rate-limits calls but does not enforce an account billing cap. Leaving either setting absent retains fully usable manual entry with a clear unconfigured message and zero address-provider calls.

Suggestions attach to Event details → Location and Street address, the registration builder's address block, and the separate attendee preview's address blocks. There are no other physical-address input surfaces in the app. After at least three characters, a 450 ms debounce requests up to five suggestions. Arrow keys, Enter and Escape work with the suggestion buttons. Stale responses are ignored. No result or provider failure leaves the user's text editable.

Selection fills available street, city, region, postal and country components. Apartment/suite/address line 2 is never replaced by provider data. (Geoapify's `address_line2` is a locality display line, not an apartment; it is deliberately ignored.) Event details keeps its legacy free-form `location` and adds an optional structured `address` object. Existing saved locations remain intact. Selecting a suggestion opens the component details, and component edits update the displayed location. Registration preview addresses remain temporary and do not create records.

The browser sends typed address text to this local server via POST. Only when configured does the server forward it to the fixed Geoapify HTTPS endpoint. The key stays server-side; it does not appear in browser responses or app request logs. Outbound requests reject redirects, validate TLS, pin a validated public IP and use bounded time/response size. Suggestion labels are rendered as text. Geoapify attribution appears with live results.

For isolated testing, `REGFIRE_ADDRESS_PROVIDER=fixture` supplies the clearly labeled synthetic `123 Example Street` result without any external call. This is a test mode, not a real lookup provider. The normal server remains unconfigured/manual.

The new Google key was restricted in Cloud Console to Places API (New) only. No fixed-IP application restriction was added because a stable public server IP has not been established for this local Mac. A live autocomplete/details request succeeded after saving the restriction (Google notes changes may take several minutes to propagate). Eight address tests and six membership transport tests passed.

After the user restarted the normal service on October 1, Chrome verification on port 8765 succeeded: Google suggestions appeared and the selected public address populated street, city, region, postal code, and country, preserving Suite 42. The preview was reloaded afterward to clear temporary answers. The earlier port-8765 restart limitation is resolved.
