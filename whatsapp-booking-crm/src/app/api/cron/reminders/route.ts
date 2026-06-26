/* ============================================================================
 * Appointment reminder cron (Recipe B / C).
 *
 * Trigger this daily (Vercel Cron, GitHub Actions, or any scheduler) with:
 *   Authorization: Bearer $CRON_SECRET
 *
 * T-24h: confirmed bookings happening tomorrow → send reminder template + tag.
 * T-0 missed: confirmed bookings dated today, not marked attended → flag for
 *             reschedule follow-up.
 * ==========================================================================*/

import { NextRequest, NextResponse } from "next/server";
import { listBookings, tagContact, updateBookingStatus } from "@/lib/store";
import { sendWhatsAppTemplate } from "@/lib/whatsapp/meta-client";
import { daysBetween } from "@/lib/dates";

export const runtime = "nodejs";

function authorized(req: NextRequest): boolean {
  const secret = process.env.CRON_SECRET;
  if (!secret) return true; // demo mode
  return req.headers.get("authorization") === `Bearer ${secret}`;
}

export async function GET(req: NextRequest) {
  if (!authorized(req)) return new NextResponse("Unauthorized", { status: 401 });

  const today = new Date().toISOString().slice(0, 10);
  const bookings = await listBookings();
  const sent: string[] = [];
  const flagged: string[] = [];

  for (const b of bookings) {
    if (!b.forDate || b.status === "cancelled") continue;
    const delta = daysBetween(b.forDate, today);
    if (delta === null) continue;

    // T-24h reminder
    if (delta === 1 && b.status === "confirmed") {
      await sendWhatsAppTemplate(b.contactPhone, "appointment_reminder_24h", [
        b.fields.name ?? "there",
        b.forDate,
        b.fields.time ?? "",
        b.fields.service ?? b.type,
      ]);
      await updateBookingStatus(b.id, "reminded");
      await tagContact(b.contactPhone, "reminded");
      sent.push(b.id);
    }

    // Missed-appointment follow-up (same-day, still not attended)
    if (delta === 0 && (b.status === "confirmed" || b.status === "reminded")) {
      await tagContact(b.contactPhone, "missed-appointment-watch");
      flagged.push(b.id);
    }
  }

  return NextResponse.json({ ok: true, remindersSent: sent.length, flagged: flagged.length, date: today });
}
