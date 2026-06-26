/* Dashboard data: recent bookings, contacts, and integration status. */
import { NextResponse } from "next/server";
import { listBookings, listContacts } from "@/lib/store";
import { aiConfigured } from "@/services/ai-service";
import { whatsappConfigured } from "@/lib/whatsapp/meta-client";

export const runtime = "nodejs";

export async function GET() {
  const [bookings, contacts] = await Promise.all([listBookings(), listContacts()]);
  return NextResponse.json({
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
