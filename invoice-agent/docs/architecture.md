# Architecture

## Scope boundary

This system starts **after** payment has already succeeded. It never
collects, retries, refunds, or reconciles payments. It only creates,
validates, sends, records, and reviews invoices. Payment-gateway code,
Accounts Payable, purchase-order matching, and bank-detail verification are
explicitly out of scope — if a future request drifts toward any of those,
that is scope creep to flag, not to quietly build.

## Component diagram

```
                         ┌───────────────────────────┐
  CRM / Website ───────▶ │  POST /api/v1/webhooks/    │  (Phase 2)
  (payment already paid) │  crm/order-paid            │
                         │  HMAC + timestamp + idemp. │
                         └──────────────┬─────────────┘
                                        │ 202 Accepted, then async
                                        ▼
                         ┌───────────────────────────┐
                         │   Celery task queue        │
                         │   (Redis broker)            │
                         └──────────────┬─────────────┘
                                        ▼
                         ┌───────────────────────────────────────────┐
                         │          Order Workflow (state machine)    │
                         │  §9 of spec — PAID_ORDER_RECEIVED → ... →  │
                         │  COMPLETED, with named failure states      │
                         └───┬─────┬─────┬─────┬─────┬─────┬─────┬───┘
                             │     │     │     │     │     │     │
                     GST Rule│ Inv#│ PDF │ ERP │Email│ CRM │ Ops │
                     Service │ Svc │ Svc │Adptr│Adptr│write│Adptr│
                             ▼     ▼     ▼     ▼     ▼     ▼     ▼
                         ┌───────────────────────────────────────────┐
                         │   Audit Service → AuditEvent (append-only) │
                         └───────────────────────────────────────────┘
                                        │
                                        ▼
                         ┌───────────────────────────────────────────┐
                         │   PostgreSQL: Customer, Product, Order,     │
                         │   Invoice, InvoiceLineItem, AuditEvent,     │
                         │   IdempotencyRecord                         │
                         │   Object storage: PDFs (private + signed URL)│
                         └───────────────────────────────────────────┘

Separately — Use Case 2:

  Upload portal / email inbox / CRM attachment / API / internal upload
                                        │
                                        ▼
                         ┌───────────────────────────────────────────┐
                         │  Intake: store original, SHA-256 hash,     │
                         │  exact-duplicate check (Phase 4)           │
                         └──────────────┬──────────────────────────┘
                                        ▼
                         ┌───────────────────────────────────────────┐
                         │  LLM Adapter (provider-agnostic):          │
                         │  Anthropic / OpenAI / OpenRouter / Gemini / │
                         │  Sarvam — strict JSON-schema extraction     │
                         │  ONLY. Recommendation, never a decision.   │
                         └──────────────┬──────────────────────────┘
                                        ▼
                         ┌───────────────────────────────────────────┐
                         │  Deterministic Decision Engine (Phase 4):   │
                         │  REJECT → HOLD_FOR_REVIEW → ACCEPT order,   │
                         │  backed by validate_invoice_math,           │
                         │  validate_required_fields,                  │
                         │  evaluate_duplicate_rules                   │
                         └──────────────┬──────────────────────────┘
                                        ▼
                  ERP draft (ACCEPT only) / review case (HOLD) /
                  audit-only record (REJECT) → Admin review queue
```

## Trust boundaries

1. **LLM ↔ backend.** The LLM (whichever provider is configured) never
   holds CRM/ERP/email/storage credentials and never calls a live tool
   directly. It receives document bytes + a system prompt + a JSON schema,
   and returns a dict. `app/services/document_review/llm_client.py` parses
   that dict and hands it to the (Phase 4) decision engine — the LLM's own
   `suggested_recommendation` field is read as input to that engine, never
   applied as the final decision.
2. **Webhook ↔ backend.** The CRM-paid-order webhook is HMAC-signed,
   timestamp-bounded (replay protection), and idempotency-keyed
   (`app/core/security.py`, Phase 2 endpoint). An invalid signature never
   reaches the workflow.
3. **Workflow ↔ ERP/Email/Operations/Product-access.** Every adapter is an
   `ABC` interface (`app/services/<name>/base.py`) with a `mock`
   implementation used until a real one is registered in that service's
   `factory.py`. The workflow layer only ever imports the interface type,
   never a concrete provider — swapping CRMs or ERPs later never touches
   workflow code.
4. **Product access.** Only `ProductAccessAdapter.enable_access()` can
   activate access, and only Operations (human action) or a configured
   automatic rule may call it — never the LLM, never a webhook directly.

## LLM provider notes (Use Case 2)

| Provider | Document input | Notes |
|---|---|---|
| Anthropic | native PDF/image `document`/`image` content blocks | matches the pattern used by both reference repos reviewed during planning |
| OpenAI | `input_file`/`input_image` via the Responses API | PDF support requires base64 `file_data` or a prior file upload |
| Gemini | inline `{"mime_type", "data"}` parts | native PDF support via `google-generativeai` |
| OpenRouter | OpenAI-compatible chat completions | PDF/vision support **varies by routed model** — check openrouter.ai/models; for scanned documents prefer pre-rasterized page images over raw PDF bytes |
| Sarvam | chat-completion-style endpoint, base64 payload | **unverified** — re-check Sarvam's current API docs for real multimodal/document support before production use; if it turns out text-only, route documents through an OCR step first (see `invoice-ocr-automation` reference reviewed during planning, which runs Tesseract/pdfplumber locally) and send extracted text instead of raw bytes |

## Failure / retry behavior

- Every webhook delivery is idempotency-keyed (`order_id + invoice_version`
  pattern, §1 of the spec). A retried stage reuses the same correlation ID
  and idempotency key; it never re-generates an invoice number or PDF, and
  never re-sends an email if `email_message_id` already exists (Phase 2+).
- ERP/email/Operations failures do not roll back prior successful steps —
  they move the invoice to a named failure state (`ERP_SYNC_FAILED`,
  `CUSTOMER_EMAIL_FAILED`, etc.) for a safe, idempotent retry.
- A tax-calculation mismatch beyond `TAX_MISMATCH_TOLERANCE` routes to
  `MANUAL_REVIEW_REQUIRED` rather than either silently accepting the
  mismatch or hard-failing the order.
- Use Case 2's decision order is always **REJECT checks → HOLD checks →
  ACCEPT** (§20) — nothing is accepted by elimination; ACCEPT is only
  reached when every required check actively passed.

## Reference material consulted while designing this

Two existing repos were reviewed (uploaded during planning, not vendored
into this repo) for working patterns, not copied verbatim:

- A local OCR/extraction/confidence-scoring/dedup pipeline (Tesseract +
  pdfplumber/PyMuPDF, no LLM) — informs the fallback/offline extraction path
  and its `exact_file` vs. `probable_invoice` duplicate-type vocabulary,
  reused here as `duplicate_type` on `ReceivedDocument` (Phase 4).
- A Claude-native-PDF extraction + rules-validation + HITL-review pipeline
  — informs `llm_client.py`'s per-provider document content-block pattern
  and the severity-typed validation-issue shape used by the (Phase 4)
  decision engine.

Both were local-folder/CLI tools with no persistent cross-run duplicate
store, no DB, and no ERP/email/CRM integration — this system's actual
duplicate detection, persistence, and integrations are new, built per the
full spec in this repo's planning conversation.
