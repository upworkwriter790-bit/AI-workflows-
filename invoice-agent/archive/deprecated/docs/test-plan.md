# Test plan

## Implemented in Phase 1 + 2 (51 tests, `backend/app/tests/`)

| Test file | Covers |
|---|---|
| `test_health.py` | `/health` returns ok; `live_invoicing_ready` correctly `false` with unset company config |
| `test_models.py` | Every Phase-1 model round-trips through SQLAlchemy: Customer, Order (unique idempotency key), Invoice + InvoiceLineItem, ReceivedDocument + Decision, AuditEvent, IdempotencyRecord |
| `test_mock_adapters.py` | CRM (verify/get/notes/ops-task, raises on unknown order), ERP (search-before-create idempotency, status update), Email (send + delivery webhook updates status), Operations + ProductAccess mocks |
| `test_security.py` | HMAC signature: valid accepted, tampered body rejected, stale timestamp rejected |
| `test_logging_redaction.py` | API-key-shaped keys redacted, GSTIN pattern redacted in free text, email pattern redacted in free text |
| `test_llm_client.py` | System-prompt company-name substitution (+ "NOT CONFIGURED" flag when unset), provider selection raises without an API key, raises on an unknown provider, selects the right provider class, JSON extraction from mixed-prose text, rejects non-JSON output |
| `test_gst_calculator.py` | Intra-state CGST+SGST 50/50 split, inter-state IGST-only, tax-inclusive back-out, discount reducing taxable value, tolerance comparison |
| `test_gst_numbering.py` | Financial-year label (Apr start, Mar = previous FY), sequential numbering, counter resets per FY |
| `test_amount_in_words.py` | Simple amount, paise, lakh/crore, zero |
| `test_order_workflow.py` | Valid order → `INVOICE_PDF_GENERATED` with a PDF whose extracted text contains the real invoice number + company name; missing company config → `VALIDATION_FAILED`; tax mismatch → `MANUAL_REVIEW_REQUIRED`; inter-state order → IGST only; invoice numbers sequential across orders; missing required item field → `VALIDATION_FAILED` |
| `test_webhooks.py` | Valid webhook → exactly one Order + one Invoice at `INVOICE_PDF_GENERATED`; repeated `event_id` → 409, no duplicate; same `order_id` different `event_id` → 409; invalid/missing signature → 401; invalid schema → 400; tax mismatch via real HTTP path → `MANUAL_REVIEW_REQUIRED` |

Run: `cd invoice-agent/backend && python -m pytest -q`

## Required by spec §23 — status after Phase 2

These are the acceptance tests the full spec calls for. Each is listed with
what it needs before it can be written for real, so nothing here is quietly
dropped.

| # | Test case | Status |
|---|---|---|
| 1 | Valid paid order creates exactly one invoice | **Implemented** — `test_webhooks.py::test_valid_webhook_creates_exactly_one_invoice` |
| 2 | Repeated paid-order webhook creates no duplicate invoice | **Implemented** — `test_webhooks.py::test_repeated_event_id_returns_409_and_creates_no_duplicate` (+ the same-order/different-event-id variant) |
| 3 | CRM webhook with invalid signature is rejected | **Implemented** — `test_security.py` (unit) + `test_webhooks.py::test_invalid_signature_returns_401` (integration) |
| 4 | Tax totals mismatch routes to manual review | **Implemented** — `test_order_workflow.py::test_tax_mismatch_routes_to_manual_review` + `test_webhooks.py::test_tax_mismatch_webhook_routes_to_manual_review` |
| 5 | ERP failure retries without reissuing invoice number/PDF | Needs the real ERP-sync workflow step (Phase 3) — Phase 2's Celery task already retries with exponential backoff on exceptions, but there's no ERP call yet to fail |
| 6 | Customer email failure is recorded and safely retryable | Email workflow step (Phase 3) |
| 7 | Operations is not notified before ERP sync succeeds | Order workflow ordering (Phase 3) |
| 8 | Product access cannot be enabled by the LLM | Enforced structurally: neither `llm_client.py` nor `order_workflow.py` (Phase 2) reference `ProductAccessAdapter` at all — needs an integration test once Phase 3 wires the real call |
| 9 | Exact duplicate document is rejected | Document-intake hashing (Phase 4) |
| 10 | Potential duplicate document is held for review | Decision engine (Phase 4) |
| 11 | Unreadable invoice is held for review | Decision engine + extraction confidence (Phase 4) |
| 12 | Missing critical field is held for review | Decision engine (Phase 4) |
| 13 | Valid received invoice/document is accepted only after rule checks pass | Decision engine (Phase 4) |
| 14 | Manual reviewer override requires reason and creates audit entry | Review API + UI (Phase 4/3) |
| 15 | Sensitive values are redacted from logs | **Implemented** — `test_logging_redaction.py` |
| 16 | Invoice PDF contains all required configured fields | **Partially implemented** — `test_order_workflow.py` extracts PDF text and checks invoice number + company name appear; full fixture-by-fixture comparison against the 20 real order examples (spec §25 build-order item 5) still needs real order data |
| 17 | Invoice numbering remains unique under concurrent requests | **Partially implemented** — `test_gst_numbering.py` + `test_order_workflow.py::test_invoice_numbers_are_sequential_across_orders` prove correctness under sequential calls using `with_for_update()`; a true concurrency test (parallel threads/processes against real PostgreSQL) still needs that real DB, since SQLite serializes writers anyway |

## Fixtures still to build (Phase 2/4)

- B2C intra-state invoice / B2B intra-state invoice / B2B inter-state invoice
- GST-inclusive price order / GST-exclusive price order
- Email failure / ERP timeout
- Exact duplicate document / near-duplicate document
- Unreadable document / wrong-recipient document / unknown-order-reference document

## Test data policy

- No real customer, GSTIN, or document data in any fixture, ever — all
  fixtures use clearly fake identifiers (`CUS-TEST-1`, GSTIN patterns that
  fail real checksum validation on purpose, `test.example.com` emails).
- Sample PDFs/images for Use Case 2 fixtures are synthetically generated,
  not scraped or sourced from real invoices.

## User-acceptance checklist (to run once Phase 2–4 land)

- [ ] A real paid-order webhook from the actual CRM produces a correct,
      GST-compliant invoice PDF reviewed by a human before go-live.
- [ ] 20 real order examples (per spec §25 build-order item 5) render
      correctly through the PDF template.
- [ ] A finance reviewer has walked through the review queue UI for at
      least one ACCEPT, one HOLD, and one REJECT case.
- [ ] Dashboards (generated/emailed/ERP-posted/access-enabled/held/
      rejected/duplicate/failed counts) match a manual count over the same
      time window.
