/* Inbox: full message thread + contact + takeover state for one conversation. */
import { NextRequest, NextResponse } from "next/server";
import { getContact, getFullHistory, getSession, isPaused } from "@/lib/store";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const business = sp.get("business") || "default";
  const phone = sp.get("phone");
  if (!phone) return NextResponse.json({ error: "phone required" }, { status: 400 });

  const [messages, contact, session, paused] = await Promise.all([
    getFullHistory(phone, business),
    getContact(phone, business),
    getSession(phone, business),
    isPaused(phone, business),
  ]);

  return NextResponse.json({ phone, messages, contact, phase: session.phase, paused });
}
