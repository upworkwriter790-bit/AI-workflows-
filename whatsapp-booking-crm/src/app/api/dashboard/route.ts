/* Dashboard data: recent bookings, contacts, and integration status (per business). */
import { NextRequest, NextResponse } from "next/server";
import { listBookings, listContacts, listProfiles } from "@/lib/store";
import { aiConfigured } from "@/services/ai-service";
import { whatsappConfigured } from "@/lib/whatsapp/meta-client";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const business = req.nextUrl.searchParams.get("business") || "default";
  const [bookings, contacts, profiles] = await Promise.all([
    listBookings(business),
    listContacts(business),
    listProfiles(),
  ]);
  return NextResponse.json({
    business,
    businesses: profiles.map((p) => ({ id: p.id, brand: p.brand, type: p.type })),
    bookings: bookings.slice(0, 50),
    contacts: contacts.slice(0, 50),
    counts: {
      bookings: bookings.length,
      contacts: contacts.length,
      confirmed: bookings.filter((b) => b.status === "confirmed").length,
    },
    integrations: {
      whatsapp: whatsappConfigured(),
      ai: aiConfigured(),
      sheets: !!process.env.GOOGLE_SHEETS_WEBHOOK_URL,
    },
  });
}
