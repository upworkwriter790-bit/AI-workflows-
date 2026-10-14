# Archived: v1 "AI-assisted post-payment invoicing" scope

Everything under `archive/deprecated/` is the **previous version** of this
project — the AR/GST/CRM/ERP/LLM-document-review system built before the
scope was changed to an Invoice Delivery Agent. It is kept here, not
deleted, so it can be restored if the product direction reverts.

**None of this code is imported, executed, or reachable from the active
`invoice-agent/backend/app/` tree.** It is dead code by isolation, not by
deletion.

## What's here and why

| Path | What it was |
|---|---|
| `README.md` | The old project README (two-use-case AR + document-review system) |
| `backend/app/api/webhooks.py` | The CRM `order.paid` webhook endpoint |
| `backend/app/models/{customer,order,invoice,invoice_line_item,invoice_sequence,product,decision,received_document}.py` | The AR/GST/document-review data model |
| `backend/app/schemas/{order_webhook,invoice_extraction_schema}.py` | CRM webhook payload schema; the Use-Case-2 LLM extraction JSON schema |
| `backend/app/services/crm/` | CRM adapter interface + mock |
| `backend/app/services/erp/` | ERP adapter interface + mock |
| `backend/app/services/gst/` | Deterministic GST tax calculator + invoice numbering |
| `backend/app/services/invoice_pdf/` | GST tax-invoice HTML/PDF renderer + amount-in-words |
| `backend/app/services/operations/` | Operations-notification adapter interface + mock |
| `backend/app/services/product_access/` | Product-access adapter interface + mock |
| `backend/app/services/document_review/` | Multi-provider LLM client (Anthropic/OpenAI/OpenRouter/Gemini/Sarvam) for invoice-document extraction |
| `backend/app/services/duplicate_detection/` | Empty package stub, never implemented, for the old Use Case 2 |
| `backend/app/prompts/invoice_document_review_system.txt` | The Claude/LLM system prompt for document review |
| `backend/app/templates/invoice.html` | The branded GST tax-invoice PDF template |
| `backend/app/tasks/order_tasks.py` | Celery task wrapping the order workflow |
| `backend/app/workflows/order_workflow.py` | The paid-order → GST calc → invoice number → PDF generation state machine |
| `backend/app/tests/{test_amount_in_words,test_gst_calculator,test_gst_numbering,test_llm_client,test_mock_adapters,test_order_workflow,test_webhooks}.py` | Tests for all of the above |
| `docs/{architecture,api-contracts,decision-rules,test-plan}.md` | Documentation describing the old scope end-to-end |

## What was NOT archived (kept active, reused as-is or adapted)

`core/config.py` (rewritten), `core/logging.py`, `core/security.py`,
`db/base.py`, `db/session.py`, `services/audit/`, `services/idempotency.py`,
`services/storage/`, `services/email/` (interface kept, content rewritten),
`tasks/celery_app.py`, `models/audit_event.py`,
`models/idempotency.py` (extended), `tests/{test_health,test_models,
test_logging_redaction,test_security}.py` (updated for the new scope),
`docs/{deployment,local-setup}.md` (kept, lightly edited), `Procfile`,
`alembic/` migration chain (new migration added on top, old migrations
kept — the migration *history* is append-only even though the old *tables*
are dropped by the new migration).
