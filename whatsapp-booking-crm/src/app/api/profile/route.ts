/* Businesses: list all, get one, create/update (returns id), delete. */
import { NextRequest, NextResponse } from "next/server";
import { generateSystemPrompt, type BusinessProfile } from "@/lib/engine";
import { deleteProfile, getProfile, listProfiles, saveProfile } from "@/lib/store";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");
  if (id) {
    const profile = await getProfile(id);
    return NextResponse.json({ profile, systemPrompt: generateSystemPrompt(profile) });
  }
  const businesses = await listProfiles();
  return NextResponse.json({ businesses });
}

export async function POST(req: NextRequest) {
  let profile: BusinessProfile;
  let id: string | undefined;
  try {
    const body = await req.json();
    profile = body.profile;
    id = body.id;
  } catch {
    return NextResponse.json({ error: "Bad JSON" }, { status: 400 });
  }
  if (!profile?.type || !profile?.brand) {
    return NextResponse.json({ error: "profile.type and profile.brand required" }, { status: 400 });
  }
  const savedId = await saveProfile(profile, id);
  return NextResponse.json({ ok: true, id: savedId, systemPrompt: generateSystemPrompt(profile) });
}

export async function DELETE(req: NextRequest) {
  const id = req.nextUrl.searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });
  await deleteProfile(id);
  return NextResponse.json({ ok: true });
}
