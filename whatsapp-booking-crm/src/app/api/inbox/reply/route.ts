/* ============================================================================
 * Inbox: send a manual (human agent) reply. Sending a manual message also
 * pauses the bot for that conversation (human takeover) so the agent and the
 * bot don't both reply. Re-enable the bot with /api/inbox/pause.
 * ==========================================================================*/

import { NextRequest, NextResponse } from "next/server";
import { appendHistory, setPaused, upsertContact } from "@/lib/store";
import { sendWhatsAppText } from "@/lib/whatsapp/meta-client";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  let body: { business?: string; phone?: string; text?: string; keepBotOn?: boolean };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Bad JSON" }, { status: 400 });
  }
  const business = body.business || "default";
  if (!body.phone || !body.text?.trim()) {
    return NextResponse.json({ error: "phone and text required" }, { status: 400 });
  }

  try {
    await sendWhatsAppText(body.phone, body.text.trim());
  } catch (err) {
    return NextResponse.json({ error: (err as Error).message }, { status: 502 });
  }

  await appendHistory(body.phone, { role: "assistant", content: body.text.trim(), via: "human" }, business);
  await upsertContact(body.phone, business);
  if (!body.keepBotOn) await setPaused(body.phone, true, business);

  return NextResponse.json({ ok: true, paused: !body.keepBotOn });
}
