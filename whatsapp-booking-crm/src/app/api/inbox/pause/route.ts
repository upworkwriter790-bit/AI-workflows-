/* Inbox: toggle bot pause (human takeover) for a conversation. */
import { NextRequest, NextResponse } from "next/server";
import { setPaused } from "@/lib/store";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  let body: { business?: string; phone?: string; paused?: boolean };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Bad JSON" }, { status: 400 });
  }
  if (!body.phone) return NextResponse.json({ error: "phone required" }, { status: 400 });
  await setPaused(body.phone, !!body.paused, body.business || "default");
  return NextResponse.json({ ok: true, paused: !!body.paused });
}
