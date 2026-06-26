/* Get / save the active business profile. */
import { NextRequest, NextResponse } from "next/server";
import { generateSystemPrompt, type BusinessProfile } from "@/lib/engine";
import { getProfile, saveProfile } from "@/lib/store";

export const runtime = "nodejs";

export async function GET() {
  const profile = await getProfile();
  return NextResponse.json({ profile, systemPrompt: generateSystemPrompt(profile) });
}

export async function POST(req: NextRequest) {
  let profile: BusinessProfile;
  try {
    profile = (await req.json()).profile;
  } catch {
    return NextResponse.json({ error: "Bad JSON" }, { status: 400 });
  }
  if (!profile?.type || !profile?.brand) {
    return NextResponse.json({ error: "profile.type and profile.brand required" }, { status: 400 });
  }
  await saveProfile(profile);
  return NextResponse.json({ ok: true, systemPrompt: generateSystemPrompt(profile) });
}
