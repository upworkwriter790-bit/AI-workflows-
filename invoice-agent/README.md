# Invoice Delivery Agent

An internal system that takes an **already-created** invoice PDF and
delivers it to a customer by email (with the PDF attached) and/or WhatsApp
(a short notification, no attachment). It keeps a private copy of the
document and a complete audit trail of every delivery attempt.

## What this system does

- Accepts an invoice PDF + recipient name/email/phone + requested channels
  via `POST /api/v1/invoice-deliveries`.
- Validates the upload (PDF only, size limit, magic bytes, sanitized
  filename) and the recipient contact fields (valid email, E.164 phone).
- Stores the original file privately and generates a delivery ID +
  correlation ID.
- Sends the invoice by email (PDF attached, optional secure download
  link) and/or a WhatsApp utility-template notification (no attachment,
  optional secure link).
- Tracks per-channel delivery status (queued/sent/delivered/read/bounced/
  failed) from provider webhooks, with a bounded, fixed retry schedule for
  transient failures.
- Supports an authorized, reason-required manual resend that creates a new
  delivery attempt without duplicating the document or the delivery record.
- Issues time-limited, download-limited secure download links that can be
  revoked and reissued.
- Keeps an append-only audit log of every state transition.
- Exposes a simple internal API (list/detail/resend/cancel) suitable for a
  dashboard, gated by three roles: ADMIN, DELIVERY_MANAGER, DELIVERY_VIEWER.

## What this system explicitly does NOT do

- No payment collection, payment verification, refunds, or reconciliation.
- No CRM or ERP integration of any kind.
- No GST/tax calculation, HSN/SAC logic, or e-invoice/IRN handling.
- No invoice PDF generation or editing — it only delivers a PDF created
  elsewhere, byte-for-byte, as supplied.
- No OCR, AI/LLM extraction, document authenticity analysis, or duplicate-
  invoice-number logic. It never inspects, interprets, or validates what's
  inside the PDF.
- No accept/hold/reject decision engine.
- No product-access activation or Operations approval workflow.
- No LLM calls of any kind — there is no LLM integration anywhere in this
  codebase.

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

49 tests. See `docs/test-plan.md` for the full list mapped to the spec's
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

The dashboard itself (list/detail/resend screens) is not yet built as a
frontend — `frontend/` remains the unbuilt Next.js scaffold from an
earlier phase. The backend API it would call (`GET /api/v1/invoice-
deliveries`, `GET /api/v1/invoice-deliveries/{id}`, the resend/cancel/
reissue actions) is implemented and tested.

## Migration notes: what was removed from active scope

This project previously included Accounts-Receivable invoicing (paid-
order webhook, GST tax calculation, invoice-number generation, branded
PDF generation) and a document-review pipeline (LLM-based extraction,
accept/hold/reject decisioning) built against CRM/ERP/Operations/product-
access adapters. All of that was removed from the active product scope —
not deleted — and lives under `archive/deprecated/` with its own notes
file. Nothing in the active `backend/app/` tree imports, executes, or
exposes any of it through an API route.
