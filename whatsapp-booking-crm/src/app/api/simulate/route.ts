/* ============================================================================
 * Stateless simulator endpoint — drives the SAME engine the live webhook uses,
 * but with the profile + session supplied by the client so nothing is persisted
 * and no Meta/AI keys are required. "What you test is what you ship."
 * ==========================================================================*/

import { NextRequest, NextResponse } from "next/server";
import { newSession, type BusinessProfile, type Session } from "@/lib/engine";
import { handleIncoming, type Mode } from "@/services/conversation";

export const runtime = "nodejs";

interface Body {
  profile: BusinessProfile;
  session?: Session;
  text: string;
  mode?: Mode;
}

export async function POST(req: NextRequest) {
  let body: Body;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Bad JSON" }, { status: 400 });
  }
  if (!body.profile || typeof body.text !== "string") {
    return NextResponse.json({ error: "profile and text required" }, { status: 400 });
  }

  const result = await handleIncoming({
    phone: "+0000000000",
    text: body.text,
    profileOverride: body.profile,
    session: body.session ?? newSession(),
    mode: body.mode ?? "deterministic", // simulator defaults to the reliable FSM
    dryRun: true,
  });

  return NextResponse.json({
    reply: result.reply,
    session: result.session,
    provider: result.provider,
    booking: result.booking ?? null,
    cancel: result.cancel ?? null,
    escalate: result.escalate ?? null,
    optOut: result.optOut ?? false,
  });
}
