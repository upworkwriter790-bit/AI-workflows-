# Decision rules

## Use Case 1 — GST tax-invoice checklist (CBIC Rule 46)

Every generated invoice must carry (Phase 2, `app/services/gst/`):

1. Supplier legal name, registered address, GSTIN.
2. A consecutive, unique-per-financial-year invoice number
   (`INVOICE_NUMBER_FORMAT`, default `INV/FY{fy_start}-{fy_end}/{seq:06d}`).
3. Invoice issue date.
4. Recipient name, address, GSTIN/UIN where registered.
5. Delivery address + state/state code where it differs from place of supply.
6. HSN (goods) or SAC (services) per line item.
7. Description of each product/service.
8. Quantity + unit for goods.
9. Total value of supply, and taxable value after discount.
10. GST rate and amount, split CGST/SGST/IGST/UTGST/cess as applicable.
11. Place of supply for inter-state transactions.
12. Reverse-charge indicator where applicable.
13. Amount payable in words.
14. Authorized-signatory / digital-signature area.
15. Template version + PDF SHA-256, for audit traceability (not prominent to the customer).

Time-limit rule (CBIC): service invoices must issue within 30 days of
supply (45 days for insurers/banks/NBFCs). **Not implemented as an
explicit check** — Phase 2's workflow always issues the invoice the same
day the paid-order webhook arrives, so this limit is satisfied by
construction, not by a runtime guard. If a future requirement introduces
delayed/batched invoice generation, this needs its own validation rule
before that happens — it is not covered today.

## Tax calculation (deterministic, never the LLM)

- Same-state supply → CGST + SGST (configured split, typically half the
  GST rate each).
- Inter-state supply → IGST (full GST rate).
- Tax-inclusive order → back out taxable value and tax split from the paid
  total.
- Tax-exclusive order → add configured tax on top of the taxable value.
- Computed total vs. the order's `grand_total` must match within
  `TAX_MISMATCH_TOLERANCE` (default `0.01`) — beyond that, the order routes
  to `MANUAL_REVIEW_REQUIRED`, never silently accepted or silently
  corrected.

## Use Case 2 — duplicate detection

- **Exact duplicate**: SHA-256 of the uploaded file matches an
  already-processed document → hard `REJECT` signal (overridable only by an
  authorized reviewer, logged).
- **Business duplicate**: normalized `(issuer_name, invoice_number,
  invoice_date, currency, total)` matches an existing active record →
  `REJECT` if all fields match; if invoice number + issuer match but the
  **total differs**, this is `HOLD_FOR_REVIEW`, not an automatic reject —
  someone may have legitimately corrected an amount.
- Normalization: lowercase, strip legal-entity suffixes
  (Inc/LLC/Ltd/Pvt/GmbH/...), collapse whitespace, strip currency
  formatting from the total before comparing.

## Use Case 2 — decision matrix

Evaluated in this fixed order — **REJECT checks first, then HOLD, then
ACCEPT only if nothing else fired**:

### A. REJECT — only on deterministic evidence

- Exact file-hash duplicate (SHA-256).
- Confirmed business duplicate (all of issuer/invoice_number/date/currency/total match).
- Issuer on a configured blocklist.
- Document recipient is definitively not this company/client where it must be.
- Invalid document type for this workflow (e.g. a non-invoice document type
  submitted where an invoice was required).
- A required reference (order/contract) definitively fails against CRM/ERP data.
- A human reviewer has explicitly rejected it.

### B. HOLD_FOR_REVIEW — the default for anything uncertain

- Any critical field (`document_type`, `issuer_name`, `recipient_name`,
  `invoice_number`, `invoice_date`, `currency`, `grand_total`, and
  `order/contract reference`/GSTIN where policy requires them) missing or
  below `CRITICAL_FIELD_CONFIDENCE_THRESHOLD` (default `0.95`).
- Arithmetic cannot be verified (subtotal + tax − discount ≠ total, or
  insufficient data to check).
- Possible but inconclusive duplicate (e.g. invoice-number+issuer match,
  total differs).
- Unknown customer/order/contract reference.
- A GST/business-rule mismatch.
- Unreadable, password-protected, corrupted, or suspicious document.
- `grand_total` exceeds `AUTO_ACCEPT_MAX_AMOUNT`.
- An ERP/CRM lookup used for validation failed (timeout, 5xx) — never treat
  a lookup failure as a pass.
- A human reviewer explicitly asked for more information.

**Low LLM-extraction confidence alone is never grounds for REJECT** — it is
always routed to HOLD per spec §4 rule 5 and §18 prompt rule 6.

### C. ACCEPT — only when everything actively passed

- No REJECT condition fired.
- No HOLD condition fired.
- Every required field present.
- CRM/customer/order match succeeded where required.
- Deterministic arithmetic check passed.
- Duplicate checks passed.
- All configured policy validations passed.

### Auto-accept ceiling

`AUTO_ACCEPT_MAX_AMOUNT` defaults to `0`, which — combined with the "total
exceeds ceiling → HOLD" rule above — means **nothing auto-accepts until a
real ceiling is configured.** This is deliberate, matching spec §4 rule 6
("never auto-accept if required fields are absent") taken to its safe
extreme: an unset ceiling is itself a kind of missing required
configuration.

## Backend validation tools the LLM may call (never execute directly)

From spec §21, implemented in Phase 4 under
`app/services/document_review/tools.py`:

1. `get_document_metadata(document_id)`
2. `get_document_file(document_id)`
3. `search_existing_documents(search_parameters)`
4. `get_crm_customer(customer_reference)`
5. `get_crm_order(order_reference)`
6. `get_erp_invoice(external_reference)`
7. `validate_invoice_math(extracted_invoice_json)`
8. `validate_required_fields(extracted_invoice_json, policy_id)`
9. `evaluate_duplicate_rules(extracted_invoice_json, document_hash)`
10. `create_review_case(document_id, reason_codes, summary)`
11. `propose_erp_update(document_id, validated_data)` — **creates a draft
    proposal only**; a separate, authorized backend workflow approves and
    finally posts it.

Every tool call is logged with a `correlation_id` via the audit service.
No tool exposes the full customer/document store to the LLM — each call is
scoped to the single document/order/customer under review.

## Reviewer override rules

- Every override requires a free-text `reason` — enforced at the API layer
  (Phase 4), not just a UI convention.
- An override writes a new `Decision` row (`decided_by=<user_id>`,
  `final_decision=<override>`) and a corresponding `AuditEvent` — the
  original LLM recommendation and the deterministic rule results from the
  prior `Decision` row are never deleted or edited, only superseded.
- A reviewer may override `HOLD_FOR_REVIEW` → `ACCEPT`/`REJECT` in either
  direction. A reviewer may **not** cause the system to skip the exact-file
  duplicate check itself — they can only decide what happens *given* that a
  duplicate was found (e.g. confirm it really is an intentional resubmission).
