# Architecture — Invoice Delivery Agent

## Scope boundary

This system never inspects, interprets, extracts, authenticates, or edits
invoice content. It receives a PDF that already exists, stores it, and
delivers it. Payment, CRM, ERP, GST, document generation, OCR/LLM
extraction, decision-making, and product-access/Operations workflows are
all out of scope — see `README.md` and `archive/deprecated/ARCHIVE_NOTES.md`.

## Component diagram

```
Internal caller (API client / future dashboard UI)
        │  POST /api/v1/invoice-deliveries  (multipart, JWT-authenticated)
        ▼
Invoice Delivery API (FastAPI, app/api/deliveries.py)
        │
        ├─ Request validation (app/schemas/delivery_request.py,
        │    app/services/file_validation.py — PDF magic bytes, size,
        │    filename sanitization, E.164 phone)
        ├─ Idempotency guard (app/services/idempotency.py — reused
        │    unchanged from earlier phases)
        ├─ Private storage (app/services/storage/ — local disk by
        │    default, S3-compatible adapter interface ready for a real one)
        ├─ InvoiceDocument + InvoiceDelivery + DeliveryAttempt rows
        ├─ Audit event log (app/services/audit/ — reused unchanged)
        └─ Celery task enqueue (app/tasks/delivery_tasks.py)
                  │
                  ▼
        app/workflows/delivery_workflow.py
                  │
                  ├──▶ Email provider adapter (app/services/email/)
                  │      - attaches the ORIGINAL stored PDF, never regenerated
                  │      - optional secure download link
                  │      - provider delivery/bounce/complaint webhooks
                  │
                  └──▶ WhatsApp provider adapter (app/services/whatsapp/)
                         - approved utility/template notification only
                         - no PDF attachment in v1
                         - optional secure download link
                         - provider sent/delivered/read/failed webhooks
        │
        ▼
Internal read API (list/detail) + resend/cancel/reissue actions,
role-gated (app/core/auth.py: ADMIN / DELIVERY_MANAGER / DELIVERY_VIEWER)
```

## Trust boundaries

1. **Intake auth.** `POST /api/v1/invoice-deliveries` requires a valid JWT
   for an `ADMIN` or `DELIVERY_MANAGER` user (spec §13's permission table:
   upload is a `DELIVERY_MANAGER`-level action, not open to `DELIVERY_VIEWER`
   or anonymous callers).
2. **Provider webhooks.** Both `/api/v1/webhooks/email` and
   `/api/v1/webhooks/whatsapp` verify the provider's signature
   (`EmailProvider.verify_webhook` / `WhatsAppProvider.verify_webhook`)
   before trusting anything in the payload, and only ever update a
   `DeliveryAttempt` they can match by the provider's own message ID —
   an unrecognized message ID is ignored, not guessed at.
3. **Secure download links.** Only a SHA-256 hash of the opaque token is
   ever persisted (`app/services/secure_links/service.py`); the raw token
   exists only in the HTTP response at creation time. `GET /d/{token}`
   needs no auth of its own — the token itself is the credential — but
   every access is checked against expiry, revocation, and remaining
   download count and is logged as an audit event.
4. **Resend/cancel/reissue.** Require `ADMIN` or `DELIVERY_MANAGER`;
   every resend requires a non-empty reason and writes an audit event
   naming the user and the reason (spec §13.3).
5. **No LLM anywhere.** There is no AI/LLM boundary to manage in this
   system at all — the single hardest trust boundary from the prior
   version of this project (LLM ↔ backend tool execution) doesn't exist
   here.

## Status rollup — documented interpretation

The spec's delivery-status enum (§8) has no single value for "every
requested channel ultimately failed" on a multi-channel delivery — only
`EMAIL_FAILED`/`WHATSAPP_FAILED` (single-channel) and
`PARTIALLY_DELIVERED` (explicitly: email succeeds, WhatsApp fails).
`app/workflows/delivery_workflow.py:recompute_delivery_status()` resolves
this by using `EMAIL_FAILED`/`WHATSAPP_FAILED` only when that is the sole
requested channel, and falling back to `PARTIALLY_DELIVERED` as the
closest named state when a multi-channel delivery fails on every channel.
The exact per-channel outcome is always visible on each `DeliveryAttempt`
row regardless of what the rollup status says — nothing is hidden by this
choice, it only affects the single summary field.

## Reused from the earlier version of this project

Per the approved migration plan, these modules were kept in place,
unchanged or lightly adapted, because they were already generic
infrastructure rather than AR/GST-specific:

- `app/core/logging.py` (redaction mechanism — key list and PII regexes
  updated for email/phone instead of email/GSTIN)
- `app/core/security.py` (HMAC + timestamp + replay-protection helper —
  not currently wired to a route in this version, kept for the next
  webhook that needs HMAC verification)
- `app/services/audit/service.py`, `app/models/audit_event.py`
- `app/services/idempotency.py`, `app/models/idempotency.py` (extended
  with a `delivery_id` column)
- `app/services/storage/` (interface + local adapter)
- `app/services/email/` (interface kept, content rewritten — now attaches
  an existing PDF instead of assuming one is generated internally)
- `app/tasks/celery_app.py`
- `Procfile`, the no-Docker deployment posture, `docs/local-setup.md`
