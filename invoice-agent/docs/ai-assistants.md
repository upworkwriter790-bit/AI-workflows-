# AI assistants — scope, safety rules, and how to disable them

This system has exactly two AI touchpoints, both for Method B
(generated invoices) only. Method A (uploaded PDFs) never involves AI
in any way — the original file is never read, altered, or regenerated.

## 1. AI Draft Prefill Assistant (Quick Create / Mode B1)

**Input**: a minimal payment snapshot (contact, amount, reference,
free-text product description) plus a short, pre-filtered list of
candidate customers/products the backend already found by exact
match (`app/services/matching/`).

**Output**: which candidate (if any) to use for the customer and
product slots, or a single clarification question. It never returns
field values itself — the backend always re-fetches the real
customer/product row from the database once a candidate_id is chosen,
and discards any id the AI returns that wasn't in the candidate list
it was given (`app/workflows/quick_create_workflow.py:resolve_quick_create`).
This means the AI literally cannot inject a price, HSN/SAC, or address
it made up — it can only point at a row that already existed.

Prompt: `backend/app/prompts/invoice_prefill_system.txt`.
Schema: `backend/app/schemas/ai_prefill_output.py` (`AIPrefillOutput`).

## 2. AI Edit-Proposal Assistant (draft review screen)

**Input**: the current draft's structured snapshot, a human's
natural-language instruction, and the exact list of fields it's
allowed to touch (`ALLOWED_EDITABLE_PATHS` in
`app/schemas/ai_edit_proposal.py`) — never the seller identity,
invoice number, status, or audit fields.

**Output**: a structured proposal (`AIEditProposalOutput`) — a list of
`{path, operation, current_value, proposed_value, reason, change_type}`
changes, or a clarification question. This is persisted as an
`InvoiceEditProposal` row with status `GENERATED` or `INVALID` — it is
never applied to the draft automatically. A separate, human-triggered
`POST .../ai-edit-proposals/{id}/apply` call is the only way a
proposal's content ever reaches the draft, and that call:

1. Re-validates every proposed path against the allowed list
   (`validate_against_allowed_paths()`) — a proposal touching a
   protected field is rejected outright at generation time, and
   re-checked again before apply.
2. Re-checks `base_draft_version_number` against the draft's *current*
   version — a proposal generated against an earlier version is
   refused (`StaleProposalError`), since the draft moved on in the
   meantime.
3. Patches only the approved fields, re-runs the same deterministic
   GST/catalog validation and recalculation as a manual edit, and
   creates a new `InvoiceDraftVersion` (`creation_reason=
   AI_PROPOSAL_APPLIED`) — it never mutates an existing version.
4. Returns the draft to `PENDING_HUMAN_REVIEW`. It never sends, never
   approves, never reserves an invoice number.

Prompt: `backend/app/prompts/invoice_draft_edit_system.txt`.
Schema: `backend/app/schemas/ai_edit_proposal.py` (`AIEditProposalOutput`).

## Hard rules enforced in code, not just in the prompt

- `app/services/ai/base.py`'s `AIProvider` interface has exactly two
  methods, `generate_prefill` and `generate_edit_proposal` — there is
  no method on it that could approve, send, delete, or write to the
  database. See `test_ai_provider_interface_has_no_delivery_or_approval_methods`
  in `app/tests/test_ai_workflow.py`.
- Every AI call goes through the real Anthropic SDK's **forced
  tool-use** (`tool_choice={"type": "tool", "name": ...}`) against a
  JSON-schema-derived tool definition — the model's only possible
  output is a single structured call matching that schema. There is no
  free-text parsing of a financial record anywhere in this path.
  (`app/services/ai/anthropic_provider.py`)
- A malformed or schema-invalid model response is never silently
  trusted — it's caught by Pydantic validation and recorded as
  `AI_EDIT_PROPOSAL_FAILED` / `status: FAILED`, not applied.
- `approve_and_finalize()` (the only function that can ever queue
  delivery) always takes an authenticated human `approved_by_user_id`
  and is only reachable through
  `require_role("ADMIN", "INVOICE_APPROVER")` at the API layer
  (`app/api/generated_invoices.py`). No code path calls it from
  anywhere inside the AI modules.

## Disabling AI editing while keeping manual review

Set `AI_EDIT_ENABLED=false`, or simply leave `AI_API_KEY` blank — both
mean `get_ai_provider()` returns `None`. The Quick Create resolver then
falls back to the same deterministic matching logic the mock provider
uses (still useful: exact email/phone/alias matches still auto-resolve,
you just lose free-text product interpretation beyond substring
matching), and the AI edit-proposal endpoints return `503`. The manual
edit, approve, reject, and cancel endpoints are completely unaffected —
human-only review was never conditional on AI being configured.
