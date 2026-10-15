# Invoice Delivery Agent — frontend

A plain HTML/CSS/JavaScript admin UI. No build step, no framework, no
npm install — open `index.html` (or serve this folder) and it talks
directly to the FastAPI backend over `fetch()`.

## Running it

1. Start the backend first (see `../backend/README.md` / the root
   `README.md`). It seeds a default admin account on first startup:
   `admin@example.com` / `ChangeMe123!` (from
   `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD` in `backend/.env`).
2. If the backend isn't running on `http://localhost:8000`, edit
   `config.js` and change `API_BASE_URL`.
3. Serve this folder with any static file server, e.g.:
   ```bash
   cd frontend
   python3 -m http.server 8012
   ```
   then open `http://localhost:8012`. (Opening `index.html` directly
   via `file://` also works in most browsers, since the backend has
   permissive CORS enabled for local use.)
4. Log in with the seeded admin, then from the **Users** screen create
   accounts with the roles you actually want to test with
   (`INVOICE_EDITOR`, `INVOICE_APPROVER`, `DELIVERY_MANAGER`,
   `DELIVERY_VIEWER`) — the human-approval workflow is the point, so
   it's worth logging in as a non-admin to see the role boundaries.

## What's here

- **Quick Create** — Mode B1: minimal payment-snapshot intake, backed
  by the AI prefill assistant and your product catalog / customer
  directory. Asks at most one clarifying question before falling back
  to the detailed form.
- **Create with detailed fields** — Mode B2: the full
  `GeneratedInvoiceDeliveryRequest` JSON, for when Quick Create can't
  resolve the order or you need complete manual control.
- **Generated-Invoice Drafts** — list + the draft review screen: PDF
  preview, line items, version history, audit timeline, manual edit,
  AI edit-assistant panel (propose → diff → apply/reject), and the
  approve/reject/cancel actions.
- **Upload Existing Invoice** — Method A: upload a PDF, choose
  channels, optionally require human approval before it sends.
- **Product Catalog** / **Customer Directory** — the trusted data the
  AI assistants are only ever allowed to pick from, never invent.
- **Users** (ADMIN only) — create accounts with the roles above.

## Notes

- This is a deliberately plain UI for testing the workflow end to end,
  not a production design system.
- Auth token is kept in `localStorage`; log out clears it.
- The draft PDF preview is fetched with your bearer token and shown via
  a `blob:` URL (an `<iframe src="...">` can't carry an Authorization
  header on its own).
