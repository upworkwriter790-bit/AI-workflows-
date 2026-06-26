/* ============================================================================
 * Google Sheets + Calendar sync.
 *
 * POSTs each booking/cancellation to a Google Apps Script web app (see
 * /scripts/google-apps-script.gs), which appends a row to your Sheet and
 * creates a Calendar event. No-ops gracefully when the webhook URL is unset.
 * ==========================================================================*/

export interface SyncPayload {
  event: "booking" | "cancellation";
  type: string; // vertical
  contact: string; // phone
  fields: Record<string, string>;
  forDate?: string; // ISO yyyy-mm-dd if normalisable
  at: string; // ISO timestamp
}

export async function syncToSheets(payload: SyncPayload): Promise<boolean> {
  const url = process.env.GOOGLE_SHEETS_WEBHOOK_URL;
  if (!url) {
    console.log("[sheets:demo]", JSON.stringify(payload));
    return false;
  }
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ secret: process.env.GOOGLE_SHEETS_WEBHOOK_SECRET || "", ...payload }),
      signal: AbortSignal.timeout(10_000),
    });
    return res.ok;
  } catch (err) {
    console.error("[sheets-sync] failed", (err as Error).message);
    return false;
  }
}
