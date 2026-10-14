# API contracts — Invoice Delivery Agent

All routes below are implemented (not planned) unless marked otherwise.
Auth: Bearer JWT, `Authorization: Bearer <token>`, issued by
`app.core.auth.create_access_token` against an `InternalUser` row — there
is no self-serve login endpoint yet (users are seeded directly; adding a
`/auth/login` endpoint is future work, not in the approved scope).

## `GET /health`

No auth. Returns `{"status": "ok", "app_env", "email_provider",
"whatsapp_provider", "storage_provider"}`.

## `POST /api/v1/invoice-deliveries`

Auth: `ADMIN` or `DELIVERY_MANAGER`. `multipart/form-data`.

Required fields: `invoice_file` (PDF), `recipient_name`,
`requested_channels` (repeated form field, one or more of `email`/
`whatsapp`), `idempotency_key`. `recipient_email` required if `email` is
requested; `recipient_phone` (E.164) required if `whatsapp` is requested.

Optional fields: `external_reference`, `invoice_number`, `source`
(`INTERNAL_UPLOAD`|`API`|`EMAIL_INTAKE`, default `INTERNAL_UPLOAD`),
`notes`, `attach_pdf_to_email` (default `true`), `include_download_link`
(default `true`), `send_whatsapp_notification` (default `true`).

| Status | Condition |
|---|---|
| 202 | Accepted; file stored, delivery created, channel dispatch enqueued |
| 200 | Same `idempotency_key` as an already-completed request — returns the existing delivery's current state, creates nothing new |
| 400 | Non-PDF file, bad magic bytes, oversized file, missing required contact field for a requested channel, invalid E.164 phone |
| 401 | Missing/invalid bearer token |
| 403 | Authenticated as `DELIVERY_VIEWER` (upload requires `ADMIN`/`DELIVERY_MANAGER`) |
| 409 | `idempotency_key` currently mid-processing by another request |
| 422 | Malformed multipart/missing required field (FastAPI's own validation) |

Response body: `{"delivery_id", "correlation_id", "status",
"requested_channels", "created_at"}`.

## `POST /api/v1/generated-invoice-deliveries`

Auth: `ADMIN` or `DELIVERY_MANAGER`. `application/json`, schema in
`app/schemas/generated_invoice_request.py` — exact shape in spec §4.
Every nested object uses `extra="forbid"`, which is also the mechanism
enforcing "do not accept card/bank/UPI/CVV data": any field not in the
schema (including those) is rejected before it reaches a database or log.

| Status | Condition |
|---|---|
| 202 | Accepted; invoice generated, PDF stored, delivery queued |
| 200 or 202 | Same `idempotency_key` as a prior successful request — returns the original invoice/delivery, generates nothing new |
| 422 | Schema violation (negative amount, missing required field, unknown field, non-PAID `payment_status`), contact-field-for-channel missing, product-catalog mismatch, seller identity not configured, or `TOTAL_MISMATCH` (computed vs. submitted totals differ beyond `TAX_TOLERANCE_AMOUNT`) |
| 401 / 403 | Same as the Method A endpoint |

A **different** `idempotency_key` reusing the same `external_reference` +
`payment_reference` pair is also a 422 — that pairing is unique per spec
§5 (`generated_invoices.uq_generated_invoice_refs`).

Response body matches spec §4's example: `{"delivery_id", "document_id",
"invoice_id", "invoice_number", "correlation_id", "status",
"requested_channels", "created_at"}`.

## `GET/POST/PATCH /api/v1/product-catalog`

`GET`: any role. `POST`/`PATCH`: `ADMIN` only. Backs the catalog
cross-check in `generated_invoice_workflow.py` — see
`docs/delivery-rules.md`.

## `GET /api/v1/invoice-deliveries`

Auth: any of `ADMIN`/`DELIVERY_MANAGER`/`DELIVERY_VIEWER`. Query params:
`status_filter`, `source`, `channel`, `search` (matches delivery ID,
external reference, invoice number, recipient email, or recipient phone).
Returns `{"deliveries": [...], "count": N}` with `recipient_email` and
`recipient_phone` masked (e.g. `b***@example.com`,
`+91*****210`).

## `GET /api/v1/invoice-deliveries/{delivery_id}`

Auth: any role. Returns full delivery detail: recipient data
(unmasked — this is the detail view for an authorized viewer, not the
masked list view), requested channels, every `DeliveryAttempt` (channel,
status, provider, provider message ID, error detail, timestamps), and the
full audit timeline merged across the delivery, its document, and every
attempt.

## `POST /api/v1/invoice-deliveries/{delivery_id}/resend`

Auth: `ADMIN` or `DELIVERY_MANAGER`. Form fields: `channels` (repeated,
`email`/`whatsapp`), `reason` (required, non-empty). Creates a new
`DeliveryAttempt` per requested channel (never a new document or
delivery) and an audit event naming the user and reason. 404 if the
delivery doesn't exist; 422 if `reason` is empty; 400 for an unknown
channel name.

## `POST /api/v1/invoice-deliveries/{delivery_id}/cancel`

Auth: `ADMIN` or `DELIVERY_MANAGER`. 409 if the delivery is already
`COMPLETED` or `CANCELLED`. Otherwise sets status to `CANCELLED` and
writes an audit event.

## `POST /api/v1/invoice-deliveries/{delivery_id}/secure-link/reissue`

Auth: `ADMIN` or `DELIVERY_MANAGER`. Revokes every currently-active secure
link for the delivery and issues a new one. Returns
`{"delivery_id", "download_url", "expires_at", "max_downloads"}`.

## `POST /api/v1/webhooks/email`

No bearer auth — authenticated via the email provider's own signature
(`EmailProvider.verify_webhook`). 401 if signature verification fails.
Body shape is provider-specific; the mock provider's test shape is
`{"message_id", "event_type": "delivered"|"bounced"|"complaint"|"failed"}`.
Returns `{"status": "processed"}` or `{"status": "ignored", "reason":
"no matching attempt for provider_message_id"}` for an unrecognized
message ID.

## `POST /api/v1/webhooks/whatsapp`

No bearer auth — authenticated via Twilio's `X-Twilio-Signature` (mock
provider always verifies true locally). Accepts Twilio's
form-urlencoded status-callback shape (`MessageSid`, `MessageStatus`) or
JSON `{"message_id", "status"}` for direct testing. Same response shape
as the email webhook.

## `GET /d/{opaque_download_token}`

No auth — the token is the credential. 404 if the token is unknown,
expired, revoked, or has exhausted its download count (the specific
reason is logged internally via an audit event, not exposed in the
response body). On success: streams the PDF directly (local storage) or
302-redirects to a short-lived signed URL (a real cloud storage adapter).

## Explicitly removed/unreachable

Per the approved scope change, these routes and the modules behind them
no longer exist in the live app and return 404:
`/api/v1/webhooks/crm/order-paid` and any CRM/ERP/GST/LLM/document-review/
Operations/product-access route. See `archive/deprecated/` for the code
that used to serve them, and
`app/tests/test_invoice_delivery_intake.py::test_removed_crm_erp_gst_llm_routes_not_reachable`
for the regression test.
