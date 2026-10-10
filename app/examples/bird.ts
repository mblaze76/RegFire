// Server-only TypeScript example. Install @messagebird/sdk in your Node project.
// Set BIRD_API_KEY privately: replace bk_xxxxxxxxx with your real Bird key.
// Importing this module does not send anything. Call only after user consent.
import { BirdClient } from "@messagebird/sdk";

function client() {
  const apiKey = process.env.BIRD_API_KEY;
  if (!apiKey || !/^bk_(us1|eu1)_[A-Za-z0-9_-]{16,}$/.test(apiKey)) {
    throw new Error("Replace bk_xxxxxxxxx with your real Bird API key in BIRD_API_KEY.");
  }
  if (process.env.REGFIRE_COMMUNICATIONS_LIVE !== "1") {
    throw new Error("Live communications delivery is disabled.");
  }
  return new BirdClient({ apiKey });
}

// The calling application must generate, expire and verify the code securely.
export async function sendVerificationCode(to: string, code: string) {
  const msg = await client().sms.send({
    to,
    template: { slug: "bird_otp_verification", parameters: { code } },
  });
  return { id: msg.id, status: msg.status };
}

export async function sendEmail(from: string, to: string, subject: string, text: string) {
  const msg = await client().email.send({ from, to: [to], subject, text });
  return { id: msg.id, status: msg.status };
}
