# Sessions and shared event branding

Sessions are event-owned, shared by attendee, exhibitor, press and custom flows. Child flow IDs resolve to their parent event; there is one agenda and one timezone. Event timezone changes revalidate existing session times. No existing event or flow is replaced by this feature.

## Organizer and attendee behavior

Open **Sessions** under an event. Create/edit/delete sessions in a draft, then choose **Save sessions**. Import UTF-8 CSV/TSV files (or paste spreadsheet text), map columns, preview errors and normalized rows, then append valid sessions. Existing sessions are retained. An import is atomic, requires the exact preview digest and current revision, rejects duplicate IDs, and is limited to 500 sessions / 2 MB. Time fields are event-local; nonexistent or ambiguous daylight-saving times are rejected. Overnight sessions must be split by date. Session prices are informational, in a supported currency, with no payment or reservations.

The same `SessionBrowser` component powers the embedded organizer preview, separate live preview and saved attendee agenda. Search title/speaker/description/track/location, filter date/track/free/paid, and add/remove sessions with overlap warnings. Saved attendee selections use local browser storage keyed by the parent event; preview selections remain temporary. The saved page reloads agenda data when returning to the tab. This is a browser-local schedule, not an attendee account or registration record. The application remains protected by its existing local organizer authentication; public attendee authentication, checkout, capacity and CEU tracking are not implemented.

The Sessions demo event uses synthetic names and content. Test fixtures belong in source control; local event database records do not.

## Shared footer

Configure the footer under **Event details → Event welcome page**. It appears on the shared welcome, registration flow previews, demographics previews and Sessions agenda. The server resolves one event-level footer for every flow. Old editors cannot overwrite it through a per-flow registration save.

The additive migration retains all normalized legacy flow footer values in `event_footers.body.legacy`. If zero or one distinct non-default footer exists, it becomes shared automatically. Multiple different non-default values produce an explicit selection/review step; the old values remain effective until resolved and remain preserved after resolution. Footer updates use a revision check. Text, support hours, contact fields, links and social links are retained; the existing footer renderer and CSS styling are reused. Edits broadcast locally to open previews.

## Standard typography and color controls

Use `WelcomeDisplay.searchResults` for every font control. Current catalog: **1,950 Google Fonts families + 5 original choices** (App default, Arial, Georgia, Trebuchet MS, Verdana), from the Google Fonts metadata endpoint retrieved October 2, 2026. Stored IDs are retained. Search results show their own typeface; result batches contain 12 matches, and only intersecting results request fonts after a 200 ms debounce. Stylesheets/font loads are cached, with explicit pending/loading/fallback feedback. No font binaries are bundled. Remote Google Fonts need network access; system fonts depend on the device.

The welcome Page title controls sit above Welcome background. Title text, font and optional explicit color persist with the event welcome settings and update both previews. Legacy titles default to “Welcome to online registration”; automatic contrast is used only when no title color has been explicitly chosen.

Use the shared color control (`color-control.js`) wherever an `input[type=color]` exists: native picker, validated six-digit hex input and a RegFire palette. Use these shared controls for future font/color settings rather than separate implementations.

## Spark

Spark is a transparent 3D-style flame character in the bottom-right corner, with shades and a speech bubble whose tail points to his smile. Seven separately rendered viewing angles in `spark-turns.png` animate a gentle turn using a small canvas. This is a sprite animation, not a live 3D mesh. Canvas/image loading failure leaves the static transparent `spark-3d.png` fallback. Pause and reduced-motion preferences show the front frame, and hidden tabs stop the animation. The character stays outside the bubble. The bubble contains sample setup prompts, local conversation and compact accessible voice, dance, send and minimize icon controls with tooltips. The bottom prototype tagline has been removed; voice's tooltip and responses still explain unavailable functionality when relevant. It is a **design prototype**. No messages or audio are sent, no microphone is activated, and no AI service is provisioned. Closing retains the conversation only for the current page lifetime; reloading clears it. Escape closes and restores focus to the launcher.

Synthetic import examples: `tests/fixtures/RegFire-Test-Sessions-and-Speakers-80.csv` contains 80 sessions across November 18–22, 2026 in America/New_York. `tests/fixtures/RegFire-Test-Members-500.csv` contains 500 fictional members using reserved example.test emails. Both were validated through the real HTTP preview/import endpoints in a temporary PostgreSQL schema. The membership examples include active (DEMO-0001), inactive (DEMO-0351), expired (DEMO-0401), and no-expiration active (DEMO-0451). These fixtures do not populate existing event data.

## Verification

81 Python tests passed, including isolated PostgreSQL persistence/restart, event/flow isolation, import mapping and validation, stale revision rejection, shared footer migration/conflict retention and welcome typography persistence. Four initial-load JavaScript regressions passed. Font loading unit checks cover on-demand caching, system fonts, unknown IDs and network failure fallback.

Chrome checks covered session creation/edit/save, CSV mapping/preview/import through pasted data, invalid-row blocking, live unsaved updates, saved schedule reload, removal/conflicts/filters, mobile preview, font-face rendering and keyboard selection, title color/font save/reload, and live shared footer rendering across welcome, attendee, exhibitor, press and Sessions pages. The browser extension's automated file chooser could not supply a local file because file-URL access was disabled; pasted CSV uses the same parser/mapping/import path. Direct CSV/TSV parsing is covered by tests.
