# RegFire communications: Bird

Bird is the default for new email and SMS configurations. RegFire's Python server calls Bird's documented regional HTTP API; it does not need a Node server or expose the key in browser JavaScript. The equivalent server-only TypeScript example is in `examples/bird.ts` and uses `@messagebird/sdk`.

## Private setup

1. Open Administration → Communications as the super administrator. Select Bird for both channels.
2. In each channel choose Replace key. **Replace `bk_xxxxxxxxx` with your real Bird API key**, entered only in the password field. Use a regional `bk_us1_…` or `bk_eu1_…` key with the corresponding email/SMS send permissions. The same appropriately scoped key can be entered for both channels, or separate keys can be used. Do not paste keys into chat, commit them, or place them in frontend code.
3. Enter the verified email sender and name, your Bird sending number for free-text SMS, and the public recovery site URL. Complete sending-domain verification and required sender/destination setup in Bird.
4. Save connections, then Validate saved setup. This checks configuration locally, not provider connectivity. Secrets stay in owner-only `.local/communications.json`, excluded from GitHub; saved keys are never returned to the page.
5. Server delivery remains gated by `REGFIRE_COMMUNICATIONS_LIVE=1`. Set that only when ready for authorized live delivery, then restart the server. No messages are sent merely by saving or validating.

Previously saved SendGrid, SMTP, or Twilio configurations continue to load. Switching to or from Bird clears the old channel credential unless you supply a replacement, so a credential cannot accidentally be sent to another provider.

## Implemented scope

- Bird email adapter is connected to existing password recovery; existing one-use token, expiry, and owner protections remain intact.
- Bird SMS adapter supports free-text messages (with explicit category) and `bird_otp_verification` template sends. Template sends omit `from`, as Bird requires for built-in templates.
- SMS campaign UI, OTP generation/verification/expiry, inbound replies, delivery webhooks, and automatic attendee messaging are not implemented by this transport integration.
- Accepted messages are recorded as submitted, never as delivered. Provider failures expose a generic error, not response contents or keys. Sends are not automatically retried.

For a separate TypeScript server, install `@messagebird/sdk`, set `BIRD_API_KEY` privately, and import the functions from `examples/bird.ts`. The example has no hard-coded recipient or verification code and sends nothing on import. The Python app uses Communications settings rather than that environment variable.

Official references: [Authentication](https://bird.com/docs/guides/authentication), [SMS](https://bird.com/docs/guides/sms/sending-sms), [Email](https://bird.com/docs/guides/email/sending-email), [TypeScript SDK](https://bird.com/docs/sdks/typescript).
