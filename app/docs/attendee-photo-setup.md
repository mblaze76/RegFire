# Attendee photo collection and Google Cloud Vision

In **Edit event → Attendee photos**, enable **Allow photo upload**, keep both content screening and the face check enabled, select sensitivity, and save the event. Existing events default to off. Settings apply to all registration flows belonging to the event.

Create a private upload link with the attendee's name and email. No email is sent automatically. The generated attendee reference is a stable photo-subject ID; it does not claim that the person completed registration or verified their email. Give the link only to the intended attendee. Links expire after seven days. **New link** rotates the token for the same attendee, invalidating the old link; **Revoke link** prevents further access while retaining the approved photo. Anyone holding a valid link can upload for that subject. Badge generation and registration completion are not included.

This installation listens only on localhost. Its links work on this computer. Remote collection requires an explicitly configured HTTPS deployment; the feature does not publish or expose the local server.

## Google setup (performed by the workspace owner)

1. Choose your Google Cloud project in the Cloud Console. Enable billing if needed, then enable **Cloud Vision API** (`vision.googleapis.com`). See [Google's setup guide](https://docs.cloud.google.com/vision/docs/setup).
2. In **APIs & Services → Credentials**, create an API key yourself. Restrict its API access to **Cloud Vision API**. For a server with a stable public egress address, add an IP-address application restriction for that server, not a browser-referrer restriction. See [Google's API key guidance](https://docs.cloud.google.com/docs/authentication/api-keys). Set appropriate API quotas and review billing; budget alerts do not constitute a usage cap.
3. Sign in to RegFire as workspace owner. Expand **Google Cloud Vision connection**, paste the key into the password field and choose **Save server key**. The key is stored only in the private server file `.local/google-vision-key`, with permissions `600`; it is never stored in an event, returned to the browser, or committed to GitHub. This credential serves the local workspace's events. Other organizers can see configured/unconfigured state but cannot read or replace the key.
4. Alternatively set `REGFIRE_GOOGLE_VISION_API_KEY` in the server environment. It overrides the file and makes the UI credential read-only. An administrator may create the private key file themselves (private `.local` directory, file mode `600`). Do not paste keys into chat, source code or shared files.
5. The configured state only confirms that a credential is present. To verify the provider, explicitly select the consent checkbox and click **Test Google connection**. This sends one generated gray square with SafeSearch and face-detection features. Google usage charges may apply. A successful test reports a response at that moment; it does not approve the test image or guarantee future availability. No test runs automatically when saving.

## Screening and retention

Supported input: static JPEG, PNG or WebP, at most 5 MB, at least 160 pixels per side, at most 6000 pixels per side and 16 megapixels. The server decodes the file, corrects EXIF orientation, strips metadata and re-encodes it as a JPEG up to 1200×1200 and 1 MB before sending those exact bytes to Google. SVG, animated, corrupt and oversized images are rejected.

Both checks are required for uploads to be enabled. [SafeSearch](https://docs.cloud.google.com/vision/docs/detecting-safe-search) checks adult, violent and racy content against the chosen likelihood threshold; medical and spoof scores are not grounds for rejection. [Face detection](https://docs.cloud.google.com/vision/docs/detecting-faces) requires exactly one detected face with confidence at least 0.80. This is not identity verification, liveness detection, or proof that an image depicts a real human. Automated decisions can be wrong; the attendee can retry with another image or contact the organizer.

Unconfigured credentials, provider errors, timeouts, incomplete responses and unknown likelihoods fail closed. No unscanned image is saved as approved. Failed replacements retain the previous approved photo. Each link allows ten attempts per UTC day and one in-flight scan at a time. Disabling the event blocks uploads at the server, including already-open links; changing policy or revoking/renewing a link during a scan prevents that scan from being saved.

Only approved, normalized photo bytes and the minimal screening outcome/policy are stored in PostgreSQL, associated with the event and stable attendee reference. No original image, EXIF, face landmarks, tokens or raw provider output is persisted. Link tokens are hashed in storage and appear only in the URL fragment and upload headers, never URL query logs. Saved photos are readable by authorized event organizers; there is no public photo URL. Event deletion cascades to its photo records. Database backups must remain private because they include attendee data and photos. Revoking or disabling collection does not delete already approved photos.

## Verification boundary

Automated tests use synthetic images, isolated database schemas and mocked Google responses. Live provider verification requires the owner's configured credential and explicit connection-test action. No Google account, billing plan or credential is created by this implementation.
