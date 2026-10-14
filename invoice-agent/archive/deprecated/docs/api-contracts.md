# API contracts

Phase 1 shipped `/health`. Phase 2 adds the paid-order webhook below.
Everything else is the **contract this system commits to building in
Phase 3+** — documented now so the shape is agreed before code exists.

## Implemented (Phase 1)

### `GET /health`

No auth. Returns:

```json
{
  "status": "ok",
  "environment": "development",
  "live_invoicing_ready": false,
  "missing_company_config": ["company_legal_name", "seller_gstin", "..."],
  "crm_provider": "mock",
  "erp_provider": "mock",
  "email_provider": "mock",
  "llm_provider": "anthropic"
}
```

`live_invoicing_ready` is `false` until every required company/tax field in
`Settings.missing_live_invoicing_fields()` is set — this is the literal
enforcement of "never invent business/tax values."

## Implemented (Phase 2)

### `POST /api/v1/webhooks/crm/order-paid`

`app/api/webhooks.py`. Auth: HMAC-SHA256 over `"{timestamp}.{raw_body}"`
using `CRM_WEBHOOK_HMAC_SECRET` (`app/core/security.py`). Headers (exact
names to be finalized against the real CRM's webhook signer once chosen):

- `X-Signature: <hex hmac>`
- `X-Timestamp: <unix epoch seconds>`

Request body: the `order.paid` schema from spec §8 (event_id, event_type,
occurred_at, order_id, customer_id, payment_status, payment_reference,
currency, customer{...}, items[...], pricing{...}) — enforced by
`app/schemas/order_webhook.py`.

Responses:

| Status | Condition |
|---|---|
| 202 | Signature valid, schema valid, not a replay → `Order`+`Invoice` rows created, Celery task enqueued |
| 400 | Schema validation failed (missing/malformed field) |
| 401 | Missing/invalid signature headers, or timestamp outside allowed skew |
| 409 | `event_id` already processing/completed, **or** an `Order` for this `order_id` already exists (covers a replay that reuses a fresh `event_id`) |

Processing past the 202 is asynchronous (Celery) — the HTTP response never
waits on GST calculation, PDF generation, or (Phase 3) ERP sync / email
send. The enqueued workflow (`app/workflows/order_workflow.py`) runs
through this state machine, stopping at `INVOICE_PDF_GENERATED`:

```
PAID_ORDER_RECEIVED -> ORDER_DATA_VALIDATED -> TAX_CALCULATED
  -> INVOICE_NUMBER_RESERVED -> INVOICE_PDF_GENERATED
```

with failure states `VALIDATION_FAILED`, `TAX_VALIDATION_FAILED`, and
`MANUAL_REVIEW_REQUIRED` (tax mismatch beyond `TAX_MISMATCH_TOLERANCE`) —
every transition writes an `AuditEvent`.

## Planned — Use Case 1 (Phase 3)

### `POST /api/v1/email/delivery-webhook` (provider-specific)

Normalizes the configured email provider's delivery/bounce webhook into
`EmailAdapter.receive_delivery_webhook()`. Exact payload shape depends on
the chosen `EMAIL_PROVIDER` (SES/Resend/SendGrid each differ) — finalized
once that provider is chosen.

### `POST /api/v1/operations/access-decision`

Internal-auth only. Body: `{"invoice_id", "action": "APPROVE_AND_ENABLE_ACCESS"|"HOLD_ACCESS"|"REJECT_ACCESS_REQUEST", "actor_id"}`.
Calls `ProductAccessAdapter.enable_access()` only on
`APPROVE_AND_ENABLE_ACCESS`, and only after ERP sync has already succeeded.

## Planned — Use Case 2 (Phase 4)

### `POST /api/v1/documents/upload`

Multipart upload. Body: file + `source_type` (`PORTAL`|`API`|`INTERNAL_UPLOAD`).
Immediately computes SHA-256, stores the original, checks exact-duplicate,
and enqueues extraction. Returns `{"document_id", "status": "DOCUMENT_RECEIVED"}`.

### `POST /api/v1/documents/email-intake` (provider webhook)

Receives a forwarded/parsed inbound-email payload from the dedicated
invoice inbox, extracts the attachment, and funnels it through the same
intake path as `/documents/upload`.

### `GET /api/v1/documents/{document_id}`

Internal-auth only. Returns `ReceivedDocument` + its `Decision` history +
audit trail. Never returns raw extraction data to an unauthenticated
caller — see redaction rules in `docs/deployment.md`.

### `POST /api/v1/documents/{document_id}/review-decision`

Internal-auth only (`FINANCE_REVIEWER`/`ADMIN` role). Body:
`{"final_decision": "ACCEPT"|"HOLD_FOR_REVIEW"|"REJECT", "reason": "<required free text>"}`.
Every override writes a `Decision` row with `decided_by=<user_id>` and an
`AuditEvent`.

## Error response shape (all endpoints, once implemented)

```json
{
  "error": {
    "code": "invalid_signature",
    "message": "human-readable, never includes secrets or full payloads",
    "correlation_id": "..."
  }
}
```

No endpoint response ever includes a GSTIN, full address, API key, or raw
document bytes in an error body — see the redaction rules shared with
logging (`app/core/logging.py`).
