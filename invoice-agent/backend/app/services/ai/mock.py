"""Deterministic, network-free stand-in for the real AI provider — used
by tests and by any environment with AI_EDIT_ENABLED=true but no real
API key wired up yet for a quick local check. It never invents a
customer/product/price — it only ever echoes back candidates the caller
already found deterministically, exactly like the real provider is
instructed to.
"""

from __future__ import annotations

from typing import Any

from app.services.ai.base import AIProvider


class MockAIProvider(AIProvider):
    name = "mock"

    def generate_prefill(self, *, system_prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        customer_candidates = context.get("customer_candidates", [])
        product_candidates = context.get("product_candidates", [])

        customer_match = {"customer_id": None, "confidence": 0.0, "match_basis": "NONE", "ambiguity_reason": None}
        if len(customer_candidates) == 1:
            customer_match = {
                "customer_id": customer_candidates[0]["id"],
                "confidence": 0.95,
                "match_basis": customer_candidates[0].get("match_basis", "USER_INPUT"),
                "ambiguity_reason": None,
            }
        elif len(customer_candidates) > 1:
            customer_match["ambiguity_reason"] = "multiple customers matched"

        product_match = {"catalog_item_id": None, "confidence": 0.0, "match_basis": "NONE", "ambiguity_reason": None}
        if len(product_candidates) == 1:
            product_match = {
                "catalog_item_id": product_candidates[0]["id"],
                "confidence": 0.9,
                "match_basis": product_candidates[0].get("match_basis", "DESCRIPTION_MATCH"),
                "ambiguity_reason": None,
            }
        elif len(product_candidates) > 1:
            product_match["ambiguity_reason"] = "multiple products matched"

        missing = []
        question = None
        if customer_match["customer_id"] is None and not context.get("minimal_input", {}).get("customer_name"):
            missing.append("recipient_identity")
        if product_match["catalog_item_id"] is None:
            missing.append("product_or_service")
            if len(product_candidates) > 1:
                question = {
                    "question": "Which item was this payment for?",
                    "field_needed": "product_or_service",
                    "answer_type": "SELECT",
                    "options": [c["display_description"] for c in product_candidates][:5],
                }
            else:
                question = {
                    "question": "What should this invoice be for?",
                    "field_needed": "product_or_service",
                    "answer_type": "TEXT",
                    "options": [],
                }

        if question:
            outcome = "NEEDS_ONE_QUESTION"
        elif missing:
            outcome = "NEEDS_DETAILED_FORM"
        elif customer_match["customer_id"] or context.get("minimal_input", {}).get("customer_name"):
            outcome = "READY_FOR_DRAFT"
        else:
            outcome = "NO_SAFE_MATCH"

        return {
            "outcome": outcome,
            "customer_match": customer_match,
            "product_match": product_match,
            "missing_critical_fields": missing,
            "single_clarification_question": question,
            "reviewer_summary": "Mock prefill — deterministic candidates only, no invented values.",
            "warnings": [],
        }

    def generate_edit_proposal(self, *, system_prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        instruction = (context.get("instruction") or "").strip()
        base_version = context.get("base_draft_version_number", 1)
        if not instruction:
            return {
                "proposal_status": "REFUSED",
                "base_draft_version_number": base_version,
                "instruction_summary": "empty instruction",
                "requires_clarification": False,
                "clarification_question": None,
                "requires_recalculation": False,
                "requires_tax_validation": False,
                "proposed_changes": [],
                "warnings": ["no instruction provided"],
                "reviewer_summary": "No instruction was given, so no proposal was made.",
            }
        return {
            "proposal_status": "REQUIRES_CLARIFICATION",
            "base_draft_version_number": base_version,
            "instruction_summary": instruction[:200],
            "requires_clarification": True,
            "clarification_question": (
                "The mock AI provider cannot interpret free text — configure a real "
                "AI_API_KEY to use natural-language edit proposals, or edit the draft manually."
            ),
            "requires_recalculation": False,
            "requires_tax_validation": False,
            "proposed_changes": [],
            "warnings": [],
            "reviewer_summary": "Mock provider: manual edit recommended.",
        }
