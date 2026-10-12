# Test plan

## Implemented in Phase 1 (25 tests, `backend/app/tests/`)

| Test file | Covers |
|---|---|
| `test_health.py` | `/health` returns ok; `live_invoicing_ready` correctly `false` with unset company config |
| `test_models.py` | Every Phase-1 model round-trips through SQLAlchemy: Customer, Order (unique idempotency key), Invoice + InvoiceLineItem, ReceivedDocument + Decision, AuditEvent, IdempotencyRecord |
| `test_mock_adapters.py` | CRM (verify/get/notes/ops-task, raises on unknown order), ERP (search-before-create idempotency, status update), Email (send + delivery webhook updates status), Operations + ProductAccess mocks |
| `test_security.py` | HMAC signature: valid accepted, tampered body rejected, stale timestamp rejected |
| `test_logging_redaction.py` | API-key-shaped keys redacted, GSTIN pattern redacted in free text, email pattern redacted in free text |
| `test_llm_client.py` | System-prompt company-name substitution (+ "NOT CONFIGURED" flag when unset), provider selection raises without an API key, raises on an unknown provider, selects the right provider class, JSON extraction from mixed-prose text, rejects non-JSON output |

Run: `cd invoice-agent/backend && python -m pytest -q`

## Required by spec §23 — not yet implementable (need Phase 2+ code first)

These are the acceptance tests the full spec calls for. Each is listed with
what it needs before it can be written for real, so nothing here is quietly
dropped.

| # | Test case | Needs |
|---|---|---|
| 1 | Valid paid order creates exactly one invoice | Webhook endpoint + order workflow (Phase 2) |
| 2 | Repeated paid-order webhook creates no duplicate invoice | Idempotency-key enforcement in the webhook handler (Phase 2) |
| 3 | CRM webhook with invalid signature is rejected | Webhook endpoint (security.py already implemented + tested) |
| 4 | Tax totals mismatch routes to manual review | GST rule service (Phase 2) |
| 5 | ERP failure retries without reissuing invoice number/PDF | Real workflow + Celery retry wiring (Phase 2/3) |
| 6 | Customer email failure is recorded and safely retryable | Email workflow step (Phase 3) |
| 7 | Operations is not notified before ERP sync succeeds | Order workflow ordering (Phase 3) |
| 8 | Product access cannot be enabled by the LLM | Enforced structurally: the LLM layer (`llm_client.py`) has no reference to `ProductAccessAdapter` at all — covered conceptually now, needs an integration test once the workflow wires real calls (Phase 3) |
| 9 | Exact duplicate document is rejected | Document-intake hashing (Phase 4) |
| 10 | Potential duplicate document is held for review | Decision engine (Phase 4) |
| 11 | Unreadable invoice is held for review | Decision engine + extraction confidence (Phase 4) |
| 12 | Missing critical field is held for review | Decision engine (Phase 4) |
| 13 | Valid received invoice/document is accepted only after rule checks pass | Decision engine (Phase 4) |
| 14 | Manual reviewer override requires reason and creates audit entry | Review API + UI (Phase 4/3) |
| 15 | Sensitive values are redacted from logs | **Implemented now** — `test_logging_redaction.py` |
| 16 | Invoice PDF contains all required configured fields | PDF template + fixture comparison (Phase 2) |
| 17 | Invoice numbering remains unique under concurrent requests | Invoice-number service with a DB-transactional sequence (Phase 2) — needs a concurrency test (e.g. `pytest-xdist` or threaded harness) once built |

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
