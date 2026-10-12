# API contracts

Phase 1 ships only `/health`. Everything else below is the **contract this
system commits to building in Phase 2+** — documented now so the shape is
agreed before code exists, per the spec's own instruction not to begin
implementation past the current phase without sign-off.

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

## Planned — Use Case 1 (Phase 2)

### `POST /api/v1/webhooks/crm/order-paid`

Auth: HMAC-SHA256 over `"{timestamp}.{raw_body}"` using
`CRM_WEBHOOK_HMAC_SECRET` (see `app/core/security.py`, already implemented
and unit-tested in Phase 1). Headers (exact names to be finalized against
the real CRM's webhook signer):

- `X-Signature: <hex hmac>`
- `X-Timestamp: <unix epoch seconds>`

Request body: the `order.paid` schema from spec §8 (event_id, event_type,
occurred_at, order_id, customer_id, payment_status, payment_reference,
currency, customer{...}, items[...], pricing{...}).

Responses:

| Status | Condition |
|---|---|
| 202 | Signature valid, schema valid, not a replay → queued for async processing |
| 400 | Schema validation failed |
| 401 | Invalid signature or timestamp outside allowed skew |
| 409 | `event_id`/idempotency key already processing or completed |

Processing is asynchronous after the 202 — the HTTP response never waits on
GST calculation, PDF generation, ERP sync, or email send.

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
