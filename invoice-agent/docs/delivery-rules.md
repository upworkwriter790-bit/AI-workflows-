# Delivery rules — Invoice Delivery Agent

(Replaces the old `decision-rules.md`, which described the GST accept/
hold/reject system that no longer exists in this project — archived at
`archive/deprecated/docs/decision-rules.md`.)

## State machine (spec §8)

```
RECEIVED -> FILE_VALIDATED -> FILE_STORED -> DELIVERY_CREATED -> QUEUED
  -> EMAIL_QUEUED and/or WHATSAPP_QUEUED
  -> EMAIL_SENT / WHATSAPP_SENT
  -> EMAIL_DELIVERED / WHATSAPP_DELIVERED (when the provider's webhook supports it)
  -> COMPLETED
```

Failure/review states: `INVALID_REQUEST`, `FILE_REJECTED`, `EMAIL_FAILED`,
`WHATSAPP_FAILED`, `PARTIALLY_DELIVERED`, `RETRY_SCHEDULED`, `CANCELLED`,
`EXPIRED`.

## Generated-invoice state machine (spec §6, Method B only)

```
REQUEST_RECEIVED -> REQUEST_VALIDATED -> AMOUNTS_CALCULATED
  -> TOTALS_VALIDATED -> INVOICE_NUMBER_RESERVED -> PDF_RENDERED
  -> PDF_STORED -> INVOICE_DOCUMENT_CREATED -> DELIVERY_CREATED
  -> DELIVERY_QUEUED -> EMAIL_QUEUED and/or WHATSAPP_QUEUED
  -> DELIVERY_COMPLETED
```

Failure states: `INVALID_REQUEST`, `CALCULATION_FAILED`,
`TOTAL_MISMATCH`, `INVOICE_NUMBER_RESERVATION_FAILED`,
`PDF_RENDER_FAILED`, `STORAGE_FAILED`, `DELIVERY_PARTIALLY_COMPLETED`,
`DELIVERY_FAILED`, `MANUAL_REVIEW_REQUIRED`.

Tracked on `GeneratedInvoice.status`, which the workflow
(`app/workflows/generated_invoice_workflow.py`) advances through
`DELIVERY_QUEUED` and then stops — delivery-level progress from that
point on (`EMAIL_SENT`, `COMPLETED`, `PARTIALLY_DELIVERED`, etc.) is
tracked on the shared `InvoiceDelivery.status` exactly as it is for
Method A, per spec §2's "both flows must share the same delivery...
implementation." This is a documented interpretation: the spec lists
`DELIVERY_COMPLETED` as a `GeneratedInvoice`-side state, but duplicating
that tracking on two rows risked the two statuses drifting apart, so
only one row (`InvoiceDelivery`) owns delivery-outcome truth.

Immutability (spec §6): once `GeneratedInvoice.generated_at` is set,
application code never updates `invoice_number`, any financial column,
`calculation_snapshot_json`, or `pdf_sha256` again. A failed email/
WhatsApp send never regenerates the PDF or reserves a new number — it
only creates/updates `DeliveryAttempt` rows. A future correction needs
its own credit-note/replacement design; this codebase does not implement
one, and `voided_at` exists on the model as a placeholder for it.

### Idempotency (Method B)

`GeneratedInvoice.idempotency_key` is DB-unique. The workflow inserts a
row for a new key and lets the unique-constraint violation (not a
separate lookup) detect a repeat. A repeat call with the same key always
returns the ORIGINAL outcome — success or failure. If the original
request failed validation, the fix is a new `idempotency_key` with
corrected data, not a retry under the same key. Separately,
`(external_reference, payment_reference)` is also DB-unique — a
*different* key reusing the same transaction pair is rejected, since that
pairing identifies one real-world transaction regardless of what key the
caller chose for it.

### Product/tax catalog cross-check

When a line item supplies `item_reference`, the workflow requires an
active `ProductCatalogItem` with that `internal_reference` whose
`hsn_or_sac_code` and `gst_rate` match the submitted values exactly — a
mismatch is `INVALID_REQUEST`. An item with no `item_reference` is
accepted using its own submitted fields, per the spec's JSON schema
(`item_reference` is optional) — tightening this to *require* a catalog
match for every line is a calling-code decision, not something this
backend enforces unilaterally today.

Implementation note: `RECEIVED` → `FILE_STORED` happen inline inside the
intake endpoint before any DB row exists for the delivery itself (the
file must be valid and stored before anything else can happen — rule 1).
`DELIVERY_CREATED` → `QUEUED` and everything after is tracked on
`InvoiceDelivery.status`, recomputed by
`app/workflows/delivery_workflow.py:recompute_delivery_status()` from
the latest `DeliveryAttempt` per channel.

## Status rollup rules (spec §8 rules 1-9)

1. File storage completes before any channel send — enforced by
   ordering in `create_invoice_delivery()`.
2. Each requested channel gets its own `DeliveryAttempt` row.
3. Email and WhatsApp dispatch independently (two separate Celery tasks);
   neither blocks the other.
4. `COMPLETED` only when every requested channel's latest attempt is in a
   success state (`SENT`/`DELIVERED`/`READ`).
5. Email succeeds + WhatsApp fails (or vice versa) → `PARTIALLY_DELIVERED`.
6. An automatic retry reuses the same `DeliveryAttempt` row, incrementing
   `attempt_number` — it never creates a new document or delivery.
7. A retry carries the same `correlation_id` (it's a property of the
   `InvoiceDelivery`, not the attempt).
8. A manual resend (`POST .../resend`) always creates a **new**
   `DeliveryAttempt` with `is_resend=True` and a `resend_reason` — never
   a new `InvoiceDocument` or `InvoiceDelivery`.
9. No automatic resend after provider acceptance unless the attempt
   failed before acceptance — the retry path only ever fires from
   `TransientProviderError` raised inside `send_invoice_email`/
   `send_invoice_notification` itself, never after a successful send.

### Documented interpretation: no enum value for "all channels failed" (multi-channel)

The spec's status enum has no single value for a multi-channel delivery
where *every* channel ultimately fails — only `EMAIL_FAILED`/
`WHATSAPP_FAILED` (used here for a single-channel delivery) and
`PARTIALLY_DELIVERED` (explicitly defined only for a mixed outcome).
`recompute_delivery_status()` falls back to `PARTIALLY_DELIVERED` for the
multi-channel-all-failed case, since it's the closest named failure state
with per-channel detail — flagged here as a judgment call, not hidden.

## Retry and idempotency policy (spec §12)

| Rule | Implementation |
|---|---|
| Transient error retry schedule | 1 min, 5 min, 30 min, 2 hr (`RETRY_SCHEDULE_MINUTES`) |
| Maximum automated retries | 4 (`RETRY_MAX_ATTEMPTS`) |
| Retryable | `TransientProviderError` — network errors, timeouts, HTTP 429, provider 5xx |
| Not retryable | `PermanentProviderError` — invalid recipient data, explicit provider rejection, bounce, template config error, unauthorized credentials |
| No duplicate send after a timeout | Each attempt's `idempotency_key` passed to the provider is `{delivery_id}:{channel}:{attempt_number}` — a provider with its own idempotency support can de-dupe on this |
| No duplicate delivery record from API retries | `idempotency_key` on `InvoiceDelivery`, enforced via `IdempotencyRecord`'s unique constraint |
| Retry visibility | Every `RETRY_SCHEDULED`, `EMAIL_FAILED`/`WHATSAPP_FAILED`, and provider webhook event writes an `AuditEvent` |

## WhatsApp-specific rules (spec §10)

- Notification only — no PDF attachment, ever, in v1.
- Sent via a provider-approved utility/template message
  (`WHATSAPP_TEMPLATE_ID`), never free-form text.
- If `WHATSAPP_PROVIDER` is unconfigured or misconfigured when a
  WhatsApp attempt is dispatched, that channel's attempt is marked
  `FAILED` with `error_code="configuration_failed"` and the email
  channel (if also requested) is dispatched independently and is
  unaffected.
- The template variables are recipient name, invoice number/reference
  (if available), and the secure download link (if enabled) — never a
  financial amount, GSTIN, or full address.

## Secure download links (spec §11)

- Token: `secrets.token_urlsafe(32)`, returned once at creation.
- Persisted: only `sha256(token)`.
- Default expiry: 7 days. Default max downloads: 3. Both configurable.
- Access checks, in order: token exists → not revoked → not expired →
  download count below max. Any failure is a 404 at the HTTP layer
  (never distinguishing *why* to an unauthenticated caller) but is logged
  internally with the real reason.
- Revoke + reissue is one authorized action
  (`POST .../secure-link/reissue`) — it revokes every currently-active
  link for that delivery before creating the replacement, so there is
  never more than one active link per delivery at a time.
