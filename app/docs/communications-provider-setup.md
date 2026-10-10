# Email and SMS setup for RegFire

The current code uses **SendGrid for email** (with an existing SMTP alternative) and **Twilio for SMS**. Provider settings are owner-only, stored on the server, and masked in responses. No live provider connection or delivery was verified in this update.

## Email

Create or use your SendGrid account. Verify the sending identity; SendGrid recommends authenticating your sending domain for production. Add only the DNS records SendGrid supplies, preserving existing mail records. Create a restricted API key with Mail Send permission, then enter it privately in RegFire Communications settings along with the verified sender email and display name. Never paste the key in a chat or commit it to GitHub.

Official instructions: [Sender identity](https://www.twilio.com/docs/sendgrid/for-developers/sending-email/sender-identity), [Domain authentication](https://www.twilio.com/docs/sendgrid/ui/account-and-settings/how-to-set-up-domain-authentication).

## SMS

Use a Twilio account, an SMS-capable sending number, the Account SID, and Auth Token. Enter the credentials privately in RegFire Communications settings. US local 10-digit business messaging requires the applicable A2P 10DLC brand and campaign registration. Other number types have their own verification requirements. Complete the requirements for the actual sending number and intended messages before sending.

Official instructions: [SMS quickstart](https://www.twilio.com/docs/messaging/quickstart), [A2P 10DLC registration](https://www.twilio.com/docs/messaging/compliance/a2p-10dlc/quickstart).

## Current boundary

Saving settings does not prove delivery. The app reports connection status truthfully. General event email/SMS campaigns and registration delivery are not automatically activated by these settings. Existing password recovery has a separate server-side live-delivery switch. A separate authorized send to an agreed test recipient is needed to prove delivery. No account creation, purchase, key creation, DNS change, or live send was performed for this change batch.
