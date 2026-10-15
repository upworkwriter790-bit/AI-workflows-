"""Strict schema for what the AI draft-edit assistant is allowed to
return. Nothing outside this shape is ever accepted — a model response
that doesn't parse against this is treated as AI_EDIT_PROPOSAL_FAILED,
never partially trusted.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

PROPOSAL_STATUSES = {"PROPOSAL_READY", "REQUIRES_CLARIFICATION", "REFUSED"}
CHANGE_TYPES = {
    "WORDING", "CUSTOMER", "ADDRESS", "LINE_ITEM", "QUANTITY", "PRICE",
    "DISCOUNT", "TAX", "REFERENCE", "DATE", "OTHER",
}
OPERATIONS = {"replace", "add", "remove"}

PROTECTED_FIELD_PATHS = {
    "invoice_number", "seller_legal_name", "seller_registered_address", "seller_gstin",
    "seller_state_name", "seller_state_code", "status", "approval_status", "idempotency_key",
    "correlation_id", "approved_by_user_id", "approved_at", "current_version_number",
    "invoice_number_assignment_stage",
}

# What a proposal is allowed to touch — kept in sync with the editable
# fields list the API passes to the AI as `allowed_editable_paths`.
ALLOWED_EDITABLE_PATHS = {
    "recipient.name", "recipient.email", "recipient.phone", "recipient.gstin",
    "recipient.billing_address", "recipient.shipping_address",
    "payment_or_order_details.payment_reference", "payment_or_order_details.payment_date",
    "external_reference", "notes",
} | {f"items[{i}].{field}" for i in range(50) for field in (
    "description", "hsn_or_sac_code", "quantity", "unit", "unit_price", "discount_amount", "gst_rate",
)}


class ProposedChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    operation: str = Field(pattern="^(replace|add|remove)$")
    current_value: str | float | int | bool | None = None
    proposed_value: str | float | int | bool | None = None
    reason: str
    change_type: str = Field(pattern="^(" + "|".join(CHANGE_TYPES) + ")$")


class AIEditProposalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_status: str = Field(pattern="^(PROPOSAL_READY|REQUIRES_CLARIFICATION|REFUSED)$")
    base_draft_version_number: int
    instruction_summary: str
    requires_clarification: bool = False
    clarification_question: str | None = None
    requires_recalculation: bool = False
    requires_tax_validation: bool = False
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reviewer_summary: str

    def validate_against_allowed_paths(self) -> list[str]:
        """Returns a list of problems; empty means every proposed change
        touches an allowed, non-protected path. Called before a proposal
        is ever shown to a human, and re-checked before apply.
        """
        problems = []
        for change in self.proposed_changes:
            base_path = change.path.lstrip("/").split("/")[0] if "/" in change.path else change.path
            if base_path in PROTECTED_FIELD_PATHS or change.path in PROTECTED_FIELD_PATHS:
                problems.append(f"proposed change touches protected field: {change.path}")
                continue
            import re

            normalized = re.sub(r"\[\d+\]", "[N]", change.path)
            allowed_normalized = {re.sub(r"\[\d+\]", "[N]", p) for p in ALLOWED_EDITABLE_PATHS}
            if normalized not in allowed_normalized:
                problems.append(f"proposed change touches a field outside allowed_editable_paths: {change.path}")
        return problems
