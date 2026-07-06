/* ============================================================================
 * Broadcast — send a pre-approved Meta template to a tagged segment of
 * contacts (e.g. post-visit feedback, re-engagement). Opted-out contacts are
 * always suppressed (WATI-style).
 *
 * POST { template, tag?, language?, variables? }  (Authorization: Bearer CRON_SECRET)
 * ==========================================================================*/

import { NextRequest, NextResponse } from "next/server";
import { listContacts } from "@/lib/store";
import { sendWhatsAppTemplate } from "@/lib/whatsapp/meta-client";

export const runtime = "nodejs";

function authorized(req: NextRequest): boolean {
  const secret = process.env.CRON_SECRET;
  if (!secret) return true; // demo mode
  return req.headers.get("authorization") === `Bearer ${secret}`;
}

export async function POST(req: NextRequest) {
  if (!authorized(req)) return new NextResponse("Unauthorized", { status: 401 });

  let body: { template?: string; tag?: string; language?: string; variables?: string[]; business?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Bad JSON" }, { status: 400 });
  }
  if (!body.template) return NextResponse.json({ error: "template required" }, { status: 400 });

  const contacts = await listContacts(body.business || "default");
  const targets = contacts.filter(
    (c) => !c.optedOut && (!body.tag || c.tags.includes(body.tag)),
  );

  let sent = 0;
  for (const c of targets) {
    try {
      await sendWhatsAppTemplate(c.phone, body.template, body.variables ?? [], body.language ?? "en");
      sent++;
    } catch (err) {
      console.error("[broadcast] send failed", c.phone, (err as Error).message);
    }
  }

  return NextResponse.json({ ok: true, segment: body.tag ?? "all", suppressed: contacts.length - targets.length, sent });
}
