/* ============================================================================
 * Google Apps Script — Sheets + Calendar sync for WhatsApp Booking CRM.
 *
 * Setup:
 *   1. Create a Google Sheet. Extensions → Apps Script. Paste this file.
 *   2. Set SHARED_SECRET below to match GOOGLE_SHEETS_WEBHOOK_SECRET in your app.
 *   3. (Optional) Set CALENDAR_ID to a calendar you own, or leave "primary".
 *   4. Deploy → New deployment → Web app → Execute as: Me, Access: Anyone.
 *   5. Copy the /exec URL into GOOGLE_SHEETS_WEBHOOK_URL in your .env.local.
 *
 * The app POSTs JSON: { secret, event, type, contact, fields, forDate, at }.
 * ==========================================================================*/

var SHARED_SECRET = "pick-any-long-random-string"; // must match the app
var CALENDAR_ID = "primary";
var SHEET_NAME = "Bookings";

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);

    if (SHARED_SECRET && body.secret !== SHARED_SECRET) {
      return json({ ok: false, error: "unauthorized" });
    }

    var sheet = getSheet();
    var f = body.fields || {};
    sheet.appendRow([
      body.at || new Date().toISOString(),
      body.event || "booking",
      body.type || "",
      body.contact || "",
      f.name || "",
      f.service || f.product || f.package || f.room || "",
      body.forDate || f.date || f.checkin || "",
      f.time || "",
      JSON.stringify(f),
    ]);

    if (body.event === "booking" && body.forDate) {
      createCalendarEvent(body);
    }

    return json({ ok: true });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  }
}

function getSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
    sheet.appendRow(["Timestamp", "Event", "Type", "Contact", "Name", "Service", "Date", "Time", "Raw"]);
  }
  return sheet;
}

function createCalendarEvent(body) {
  try {
    var cal = CALENDAR_ID === "primary" ? CalendarApp.getDefaultCalendar() : CalendarApp.getCalendarById(CALENDAR_ID);
    if (!cal) return;
    var f = body.fields || {};
    var title = (body.type || "Booking") + " — " + (f.name || body.contact || "");
    var start = parseStart(body.forDate, f.time);
    var end = new Date(start.getTime() + 60 * 60 * 1000); // 1h default
    cal.createEvent(title, start, end, {
      description: "Booked via WhatsApp\n" + JSON.stringify(f, null, 2),
    });
  } catch (err) {
    // Don't fail the whole request if calendar write fails.
  }
}

function parseStart(dateStr, timeStr) {
  var d = new Date(dateStr + "T09:00:00");
  if (timeStr) {
    var m = String(timeStr).match(/(\d{1,2})(?::(\d{2}))?\s*(am|pm)?/i);
    if (m) {
      var h = parseInt(m[1], 10);
      var min = m[2] ? parseInt(m[2], 10) : 0;
      var ap = (m[3] || "").toLowerCase();
      if (ap === "pm" && h < 12) h += 12;
      if (ap === "am" && h === 12) h = 0;
      d.setHours(h, min, 0, 0);
    }
  }
  return d;
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
