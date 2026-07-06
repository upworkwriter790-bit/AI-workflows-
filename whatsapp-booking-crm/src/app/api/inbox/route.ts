/* Inbox: list conversations for a business. */
import { NextRequest, NextResponse } from "next/server";
import { listConversations, listProfiles } from "@/lib/store";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const business = req.nextUrl.searchParams.get("business") || "default";
  const [conversations, profiles] = await Promise.all([listConversations(business), listProfiles()]);
  return NextResponse.json({
    business,
    businesses: profiles.map((p) => ({ id: p.id, brand: p.brand, type: p.type })),
    conversations,
  });
}
