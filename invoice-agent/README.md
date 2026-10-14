# Invoice Delivery Agent

An internal system with **two invoice intake methods** that both end in
the same delivery pipeline:

- **Method A — existing-invoice delivery**: an already-created PDF is
  uploaded; the system stores it and delivers it by email (PDF attached)
  and/or WhatsApp (a short notification, no attachment). The PDF is never
  regenerated or altered.
- **Method B — payment-details-to-invoice delivery**: payment/order
  details (already paid elsewhere — this system never collects or
  verifies payment) are submitted; the system generates a GST tax-invoice
  PDF using deterministic backend tax rules and a fixed template, stores
  it, and delivers it through the exact same pipeline as Method A.

Both methods keep a private copy of the document and a complete audit
trail of every delivery attempt.

## What this system does

- **Method A**: `POST /api/v1/invoice-deliveries` (multipart) — upload an
  existing PDF + recipient name/email/phone + requested channels.
  Validates the upload (PDF only, size limit, magic bytes, sanitized
  filename) and recipient contact fields (valid email, E.164 phone).
- **Method B**: `POST /api/v1/generated-invoice-deliveries` (JSON) —
  submit payment/order details + recipient + line items. Validates the
  request, calculates GST deterministically (no LLM), reserves a unique
  invoice number, renders a fixed HTML/CSS template to PDF, then hands
  off to the same delivery pipeline as Method A.
- Both: stores the PDF privately, generates a delivery ID + correlation
  ID, sends by email (PDF attached, optional secure download link)
  and/or WhatsApp (utility-template notification only, no attachment),
  tracks per-channel delivery status from provider webhooks with a
  bounded fixed retry schedule, supports an authorized reason-required
  manual resend, issues revocable/reissuable secure download links, and
  keeps an append-only audit log of every state transition.
- A simple internal API (list/detail/resend/cancel — shared by both
  methods) suitable for a dashboard, gated by three roles: ADMIN,
  DELIVERY_MANAGER, DELIVERY_VIEWER.
- A product/tax catalog (`GET/POST/PATCH /api/v1/product-catalog`,
  ADMIN-gated for writes) so a Method-B caller references an approved
  HSN/SAC + GST rate by `item_reference` instead of inventing one per
  invoice.

## What this system explicitly does NOT do

- No payment collection, payment verification, refunds, or reconciliation.
- No CRM or ERP integration of any kind, no accounting journal posting.
- No invoice authenticity/fake-invoice checking.
- No OCR, AI/LLM extraction, or document-extraction logic of any kind.
  Method B's tax calculation is 100% deterministic backend code — no LLM
  calculates tax, invents a field, or creates an invoice number, ever.
- No accept/hold/reject decision engine.
- No product-access activation or Operations approval workflow.
- No LLM calls of any kind — there is no LLM integration anywhere in this
  codebase.
- Method A never regenerates or edits the uploaded PDF. Method B never
  issues a second invoice number or PDF for the same `idempotency_key`.

**This is an implementation tool, not legal or tax advice.** Before
production use, a qualified CA/GST professional must approve: the tax
rules and rounding strategy (`app/services/invoicing/calculator.py`), the
invoice template (`app/templates/generated_invoice.html`), the seller
GSTIN/state configuration, the product/tax catalog's HSN/SAC mapping, and
whether GST e-invoicing (IRN) applies to this business — IRN/IRP
integration is explicitly out of scope today.

See `archive/deprecated/ARCHIVE_NOTES.md` for what this project used to be
and why those capabilities were removed from active scope rather than
deleted outright.

## Local setup

```bash
cd invoice-agent/backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env            # sqlite default works for local dev
python -m alembic upgrade head
uvicorn app.main:app --reload      # http://localhost:8000/health
```

No Docker. For Postgres/Redis setup instead of the SQLite/no-queue local
default, see `docs/local-setup.md`.

### Running the background worker (needed for real deliveries)

```bash
celery -A app.tasks.celery_app worker --loglevel=info
```

In tests, Celery's `.delay()` calls are monkeypatched to run synchronously
against the test database — no broker is required to run the test suite.

### Tests

```bash
cd invoice-agent/backend
source .venv/bin/activate
python -m pytest -q
```

74 tests. See `docs/test-plan.md` for the full list mapped to the spec's
required test cases.

## Required environment variables

See `.env.example` at the repo root. Everything defaults to `mock`
providers and a local SQLite database — nothing is sent to a real inbox
or phone number, and no real cloud storage is touched, until you set real
provider credentials.

Categories: app/db/queue, storage, upload limits, email provider, WhatsApp
provider, retry policy, company identity (used only in email/WhatsApp
copy, never written onto the invoice itself).

## File upload API example

```bash
curl -X POST http://localhost:8000/api/v1/invoice-deliveries \
  -H "Authorization: Bearer <jwt-for-an-ADMIN-or-DELIVERY_MANAGER-user>" \
  -F "invoice_file=@/path/to/invoice.pdf;type=application/pdf" \
  -F "recipient_name=Jane Buyer" \
  -F "recipient_email=jane@example.com" \
  -F "recipient_phone=+919876543210" \
  -F "requested_channels=email" \
  -F "requested_channels=whatsapp" \
  -F "idempotency_key=order-10452-invoice-send-1" \
  -F "invoice_number=INV-2026-0045"
```

Response:

```json
{
  "delivery_id": "b1a2...",
  "correlation_id": "corr_...",
  "status": "QUEUED",
  "requested_channels": ["email", "whatsapp"],
  "created_at": "2026-10-14T10:00:00Z"
}
```

A repeated call with the same `idempotency_key` returns the same
`delivery_id` and does not create a second delivery.

## Generated-invoice API example (Method B)

```bash
curl -X POST http://localhost:8000/api/v1/generated-invoice-deliveries \
  -H "Authorization: Bearer <jwt-for-an-ADMIN-or-DELIVERY_MANAGER-user>" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "order-10452-invoice-1",
    "external_reference": "ORD-10452",
    "recipient": {
      "name": "Jane Buyer", "email": "jane@example.com", "phone": "+919876543210",
      "billing_address": {"line1": "1 MG Road", "city": "Mumbai", "state": "Maharashtra", "state_code": "27", "postal_code": "400001", "country": "India"}
    },
    "payment_or_order_details": {
      "payment_reference": "PAY-98765", "payment_date": "2026-10-14", "currency": "INR",
      "tax_inclusive": false, "subtotal": 1000.00, "discount_total": 0, "tax_total": 180.00, "grand_total": 1180.00,
      "payment_status": "PAID"
    },
    "items": [
      {"item_reference": "COURSE-PRO-001", "description": "Professional Plan", "product_type": "SERVICE", "hsn_or_sac_code": "9983", "quantity": 1, "unit": "Nos", "unit_price": 1000.00, "gst_rate": 18.00}
    ],
    "delivery": {"requested_channels": ["email", "whatsapp"]}
  }'
```

Response:

```json
{
  "delivery_id": "invdel_123",
  "document_id": "doc_123",
  "invoice_id": "invoice_123",
  "invoice_number": "INV/FY26-27/000001",
  "correlation_id": "corr_123",
  "status": "DELIVERY_QUEUED",
  "requested_channels": ["email", "whatsapp"],
  "created_at": "2026-10-14T10:00:00Z"
}
```

The same `idempotency_key` always returns the same invoice/delivery —
never a second invoice number, PDF, or send. Submitting a **different**
`idempotency_key` with the same `external_reference` + `payment_reference`
is rejected (422) — that pairing is unique per spec §5; use the original
key to retrieve the existing invoice, or a documented correction/credit-
note process (not yet built) for a genuine correction.

If any `item_reference` is supplied, it must match an active entry in the
product/tax catalog (`GET /api/v1/product-catalog`) on both
`hsn_or_sac_code` and `gst_rate` — a mismatch is rejected (422) rather
than silently trusting the caller's submitted values. An item with no
`item_reference` is still accepted using its own submitted HSN/SAC and
GST rate, per spec §4's schema — the catalog is advisory unless you
choose to require `item_reference` for every line in your own calling
code.

## Email provider setup

`EMAIL_PROVIDER=mock` (default) uses an in-memory adapter — safe for local
dev and CI. To use a real provider, implement `EmailProvider`
(`app/services/email/base.py`) for it and register it in
`app/services/email/factory.py`; no real provider ships yet. Required
config: `EMAIL_FROM_NAME`, `EMAIL_FROM_ADDRESS`, `EMAIL_REPLY_TO_ADDRESS`,
`EMAIL_API_KEY`, `EMAIL_WEBHOOK_SIGNING_SECRET`.

## WhatsApp provider setup

`WHATSAPP_PROVIDER=mock` (default) uses an in-memory adapter.
`WHATSAPP_PROVIDER=twilio` uses the included Twilio WhatsApp adapter
(`app/services/whatsapp/twilio_provider.py`) once you set
`WHATSAPP_ACCOUNT_SID`, `WHATSAPP_AUTH_TOKEN`, `WHATSAPP_FROM_NUMBER`, and
`WHATSAPP_TEMPLATE_ID` (a Twilio Content Template SID for your approved
utility template — Twilio requires an approved template for any
business-initiated WhatsApp message). You still need to register and get
that template approved with Twilio/Meta yourself; nothing here does that
for you.

## GST tax calculation (Method B)

Deterministic, Decimal-based, no LLM involved — `app/services/invoicing/
calculator.py`. Same-state (seller state code == recipient state code) →
CGST+SGST split 50/50; different state → IGST. Tax-inclusive input backs
out the taxable value; tax-exclusive input adds GST on top. Every input
and computed result is captured in `calculation_snapshot_json` on the
`GeneratedInvoice` row for audit. Computed subtotal/discount/tax/grand
totals are compared against the submitted ones within
`TAX_TOLERANCE_AMOUNT` (default 0.01) — a mismatch beyond that rejects
the request (`TOTAL_MISMATCH`, HTTP 422) rather than generating and
sending an invoice with numbers that don't reconcile.

## Invoice numbering (Method B only)

`app/services/invoicing/numbering.py` — India financial-year-scoped
(April–March, `FINANCIAL_YEAR_START_MONTH`), a DB row lock
(`with_for_update()`) guarantees no two concurrent requests get the same
number, enforced again by a DB-level unique constraint on
`generated_invoices.invoice_number`. A number is reserved only after
totals validation passes, and is never reused or altered once issued —
Method A's existing-PDF uploads never go through this at all (an
uploaded PDF may carry its own `invoice_number` purely as metadata).

## Product/tax catalog

`GET/POST/PATCH /api/v1/product-catalog` (list: any role; create/update:
`ADMIN` only). Each entry: `internal_reference`, `display_description`,
`product_type`, `hsn_or_sac_code`, `unit`, `unit_price`, `gst_rate`,
`tax_category`, `active`. **You must populate this catalog with your
real, CA-approved products/services before production use** — an empty
catalog means Method B accepts whatever HSN/SAC and GST rate a caller
submits for any line item with no `item_reference`, which is a gap you
close by requiring `item_reference` in your own calling code, not
something this backend forces today.

## Webhook setup and verification

- `POST /api/v1/webhooks/email` — your email provider's delivery/bounce/
  complaint webhook. Verified via `EmailProvider.verify_webhook()` before
  anything in the payload is trusted.
- `POST /api/v1/webhooks/whatsapp` — Twilio's status-callback webhook.
  Verified via Twilio's `X-Twilio-Signature` header and
  `WHATSAPP_AUTH_TOKEN` (the mock provider's `verify_webhook` always
  returns `True`, since there's no real signature to check locally).

Both routes look up the matching `DeliveryAttempt` by the provider's own
message ID and ignore events for a message ID they don't recognize,
rather than guessing.

## Retry policy

Transient errors (network errors, timeouts, HTTP 429, provider 5xx) retry
on a fixed schedule: 1 minute, 5 minutes, 30 minutes, then 2 hours — 4
attempts maximum (`RETRY_MAX_ATTEMPTS`, `RETRY_SCHEDULE_MINUTES`).
Non-retryable errors (invalid recipient data, an explicit provider
rejection, a bounced email, a template configuration error, unauthorized
credentials) go straight to `FAILED` — see
`app/services/provider_errors.py` for the two exception types providers
raise to signal which kind of failure occurred. Every retry decision is
recorded in the audit timeline.

## Secure-link policy

- Default validity: 7 days (`SECURE_LINK_EXPIRY_DAYS`).
- Default max downloads: 3 (`SECURE_LINK_MAX_DOWNLOADS`).
- Only the SHA-256 hash of the token is stored — the raw token is returned
  exactly once, at creation time.
- `GET /d/{token}` validates expiry, revocation, and remaining downloads
  before streaming the file (local storage) or redirecting to a
  short-lived signed URL (a real cloud storage adapter, once implemented).
- `POST /api/v1/invoice-deliveries/{id}/secure-link/reissue` revokes any
  active link for that delivery and issues a new one.

## Dashboard roles

| Role | Permissions |
|---|---|
| `ADMIN` | Everything, including settings |
| `DELIVERY_MANAGER` | Upload, view, resend, revoke/reissue secure links |
| `DELIVERY_VIEWER` | View deliveries and status only |

The dashboard itself (list/detail/resend screens, the "Send Existing
Invoice" and "Create and Send Invoice" pages) is not yet built as a
frontend — `frontend/` remains the unbuilt Next.js scaffold from an
earlier phase. The backend API both pages would call (Method A's upload
endpoint, Method B's generate-and-deliver endpoint, `GET /api/v1/invoice-
deliveries`, `GET /api/v1/invoice-deliveries/{id}`, the resend/cancel/
reissue actions, the product-catalog endpoints) is implemented and
tested.

## Migration notes: what was removed from active scope

This project previously included a different Accounts-Receivable design
(a CRM paid-order **webhook** triggering invoice generation) and a
document-review pipeline (LLM-based extraction, accept/hold/reject
decisioning) built against CRM/ERP/Operations/product-access adapters.
That webhook-driven version was removed from the active product scope —
not deleted — and lives under `archive/deprecated/` with its own notes
file. The current Method B (generated invoices) is a **new, independent
implementation** of GST calculation + numbering + PDF generation, built
fresh for this scope rather than restored from the archive, triggered by
an authorized API call instead of a CRM webhook. Nothing in the active
`backend/app/` tree imports, executes, or exposes any CRM/ERP/payment-
gateway/LLM/OCR capability through an API route.
