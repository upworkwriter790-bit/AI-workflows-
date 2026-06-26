/* ============================================================================
 * Meta WhatsApp Cloud API webhook.
 *
 *   GET  — verification handshake (hub.challenge) when you register the webhook.
 *   POST — inbound messages: verify HMAC, run the conversation orchestrator,
 *          send the reply back via the Cloud API.
 * ==========================================================================*/

import { NextRequest, NextResponse } from "next/server";
import {
  sendWhatsAppText,
  verifyWebhookChallenge,
  verifyWebhookSignature,
} from "@/lib/whatsapp/meta-client";
import { handleIncoming } from "@/services/conversation";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const challenge = verifyWebhookChallenge(
    sp.get("hub.mode"),
    sp.get("hub.verify_token"),
    sp.get("hub.challenge"),
  );
  if (challenge) return new NextResponse(challenge, { status: 200 });
  return new NextResponse("Forbidden", { status: 403 });
}

interface WaMessage {
  from: string;
  type: string;
  text?: { body: string };
  button?: { text: string };
  interactive?: {
    button_reply?: { title: string };
    list_reply?: { title: string };
  };
}

/** Pull the best-effort text out of the various inbound message shapes. */
function extractText(m: WaMessage): string | null {
  if (m.type === "text") return m.text?.body ?? null;
  if (m.type === "button") return m.button?.text ?? null;
  if (m.type === "interactive") {
    return m.interactive?.button_reply?.title ?? m.interactive?.list_reply?.title ?? null;
  }
  return null;
}

export async function POST(req: NextRequest) {
  const raw = await req.text();

  if (!verifyWebhookSignature(raw, req.headers.get("x-hub-signature-256"))) {
    return new NextResponse("Invalid signature", { status: 401 });
  }

  let payload: unknown;
  try {
    payload = JSON.parse(raw);
  } catch {
    return new NextResponse("Bad JSON", { status: 400 });
  }

  // Acknowledge fast; process inline (sends are quick). For heavy workloads,
  // enqueue here and return 200 immediately.
  try {
    const entries = (payload as { entry?: unknown[] })?.entry ?? [];
    for (const entry of entries) {
      const changes = (entry as { changes?: unknown[] })?.changes ?? [];
      for (const change of changes) {
        const value = (change as { value?: { messages?: WaMessage[] } })?.value;
        const messages = value?.messages ?? [];
        for (const msg of messages) {
          const text = extractText(msg);
          if (!text) continue;
          const result = await handleIncoming({ phone: msg.from, text });
          if (result.reply) await sendWhatsAppText(msg.from, result.reply);
        }
      }
    }
  } catch (err) {
    console.error("[webhook] processing error", err);
    // Still 200 so Meta doesn't disable the webhook on a transient error.
  }

  return NextResponse.json({ received: true });
}
