# LinkedIn Profile Audit

Paste a LinkedIn profile's content (or a link) and/or drag-and-drop a document
(Excel, Word, PDF, CSV, or an image/screenshot of the profile), run the audit,
and get back a scored report: an overall score (0-100), a rating band, what's
dragging the score down (with the exact phrases flagged), what's already
working in your favor for engagement, and concrete recommendations to push
the score toward 95+.

This is phase 1 of the tool (the audit screen itself). Further sections/pages
will be added on top of this later.

## How it's built

- `backend/` — Node.js/Express API. Receives the pasted content and/or
  uploaded file, extracts text (or reads images/PDFs directly), sends it to
  Claude with a structured scoring rubric, and returns a JSON report.
- `frontend/` — React (Vite) UI: the paste box, the drag-and-drop upload
  zone (5MB limit, upload confirmation), the "Test the Audit" button, and the
  report view (score gauge, band, strengths, flagged weaknesses,
  recommendations).

## Supported uploads

`.pdf`, `.doc`, `.docx`, `.xlsx`, `.xls`, `.csv`, `.png`, `.jpg`, `.jpeg`,
`.webp`, `.gif` — max **5MB** per file (enforced both in the browser and on
the server).

**Google Sheets / Google Docs**: these are cloud documents, not local files,
so there's nothing to "drag" until you export one. Either export the sheet/doc
as `.xlsx`/`.csv`/`.docx`/`.pdf` and drop that, or paste a **published/shared
link** into the top paste box and paste the actual text alongside it.

**LinkedIn profile links**: the app does not scrape live LinkedIn pages
(LinkedIn requires login and blocks automated scraping — attempting it would
violate their terms of use). Paste the URL for reference if you like, but for
a real audit, paste the profile's actual text (About section, headline,
experience bullets, etc.) or upload a screenshot/export of the profile.

## Setup

### Backend

```bash
cd backend
npm install
cp .env.example .env   # then set ANTHROPIC_API_KEY
npm run dev
```

Runs on `http://localhost:5000` by default.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173` by default and proxies `/api/*` requests to
the backend.

## Scoring bands used in the report

| Score  | Band                                        |
|--------|----------------------------------------------|
| 0–32   | Very Poor                                     |
| 33–49  | Poor                                          |
| 50–74  | Good — solid, but there's clear room to improve |
| 75–100 | Very Good — already strong, can be optimized toward 95+ |
