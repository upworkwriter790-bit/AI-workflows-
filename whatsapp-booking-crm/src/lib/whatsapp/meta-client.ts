/* ============================================================================
 * Meta WhatsApp Cloud API client (the official Business API).
 *
 * Outbound text + template sends, plus HMAC-SHA256 signature verification for
 * inbound webhooks. In "demo mode" (no token configured) sends are logged and
 * skipped so the rest of the pipeline still runs locally.
 * ==========================================================================*/

import crypto from "node:crypto";

const API_VERSION = process.env.WHATSAPP_API_VERSION || "v21.0";

function creds() {
  return {
    token: process.env.WHATSAPP_ACCESS_TOKEN,
    phoneId: process.env.WHATSAPP_PHONE_NUMBER_ID,
  };
}

export function whatsappConfigured(): boolean {
  const { token, phoneId } = creds();
  return !!token && !!phoneId;
}

/** Send a plain text WhatsApp message. */
export async function sendWhatsAppText(to: string, body: string): Promise<void> {
  const { token, phoneId } = creds();
  if (!token || !phoneId) {
    console.log(`[whatsapp:demo] → ${to}: ${body}`);
    return;
  }
  const res = await fetch(`https://graph.facebook.com/${API_VERSION}/${phoneId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      messaging_product: "whatsapp",
      recipient_type: "individual",
      to,
      type: "text",
      text: { preview_url: false, body },
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`WhatsApp send failed (${res.status}): ${err}`);
  }
}

/**
 * Send a pre-approved Meta template (used by broadcasts / reminders).
 * `variables` fill the body's {{1}}, {{2}}… placeholders in order.
 */
export async function sendWhatsAppTemplate(
  to: string,
  templateName: string,
  variables: string[] = [],
  language = "en",
): Promise<void> {
  const { token, phoneId } = creds();
  if (!token || !phoneId) {
    console.log(`[whatsapp:demo] template "${templateName}" → ${to} vars=${JSON.stringify(variables)}`);
    return;
  }
  const components = variables.length
    ? [{ type: "body", parameters: variables.map((v) => ({ type: "text", text: v })) }]
    : [];
  const res = await fetch(`https://graph.facebook.com/${API_VERSION}/${phoneId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      messaging_product: "whatsapp",
      to,
      type: "template",
      template: { name: templateName, language: { code: language }, components },
    }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`WhatsApp template send failed (${res.status}): ${err}`);
  }
}

/**
 * Verify the X-Hub-Signature-256 header against the raw request body using
 * META_APP_SECRET. Returns true if no secret is configured (demo mode), so the
 * pipeline is testable locally — set the secret in production.
 */
export function verifyWebhookSignature(rawBody: string, signatureHeader: string | null): boolean {
  const secret = process.env.META_APP_SECRET;
  if (!secret) return true; // demo mode
  if (!signatureHeader) return false;
  const expected = "sha256=" + crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
  const a = Buffer.from(expected);
  const b = Buffer.from(signatureHeader);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

/** GET webhook verification handshake (hub.challenge). */
export function verifyWebhookChallenge(
  mode: string | null,
  token: string | null,
  challenge: string | null,
): string | null {
  const verifyToken = process.env.WHATSAPP_VERIFY_TOKEN;
  if (mode === "subscribe" && token && token === verifyToken) return challenge;
  return null;
}
