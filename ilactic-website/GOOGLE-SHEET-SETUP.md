# Join Community → Google Sheet setup

This connects the "Join community" popup (name + WhatsApp number) to a Google
Sheet you own. No server needed — Google Apps Script does the work for free.

## 1. Create the sheet
1. Go to [sheets.google.com](https://sheets.google.com) → create a new blank sheet.
2. Name it something like "Ilactic Community Leads".
3. In row 1, add headers: `Timestamp | Name | Phone | Page`

## 2. Add the script
1. In the sheet, go to **Extensions → Apps Script**.
2. Delete whatever's in the editor and paste this:

```javascript
function doPost(e) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const data = JSON.parse(e.postData.contents);
  sheet.appendRow([
    data.ts || new Date().toISOString(),
    data.name || "",
    data.phone || "",
    data.page || "",
  ]);
  return ContentService.createTextOutput(
    JSON.stringify({ status: "ok" })
  ).setMimeType(ContentService.MimeType.JSON);
}
```

3. Click **Save** (the disk icon), name the project anything.

## 3. Deploy as a web app
1. Click **Deploy → New deployment**.
2. Click the gear icon next to "Select type" → choose **Web app**.
3. Settings:
   - **Execute as:** Me
   - **Who has access:** Anyone
4. Click **Deploy**. Google will ask you to authorize it — approve it (it's your own script, running under your own account).
5. Copy the **Web app URL** it gives you — looks like
   `https://script.google.com/macros/s/AKfycb.../exec`

## 4. Plug the URL into the site
Open [js/script.js](js/script.js) and find this line (in the "Join Community popup" section near the top):

```javascript
const SHEET_ENDPOINT = "";
```

Paste your URL in between the quotes:

```javascript
const SHEET_ENDPOINT = "https://script.google.com/macros/s/AKfycb.../exec";
```

Save, refresh the site, and test the popup — a new row should appear in your
sheet within a couple of seconds of submitting.

## Notes
- The site sends the request with `mode: "no-cors"`, so the browser can't read
  Google's response — this is normal for Apps Script web apps and the submission
  still goes through. You'll know it worked by checking the sheet itself.
- If you ever redeploy the script (not just edit it — Apps Script needs a **new
  deployment** version to pick up code changes), you'll get a new URL and need
  to update `SHEET_ENDPOINT` again. Editing + saving alone does NOT update a
  live deployment.
- The WhatsApp group redirect is a separate placeholder (`WHATSAPP_GROUP_URL`
  in the same file) — add your actual group invite link there whenever you have it.
