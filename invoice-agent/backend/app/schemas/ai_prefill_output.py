"""Strict schema for the AI prefill assistant (Quick Create). Trimmed
from the full reference spec to what this app actually acts on: a
customer match, a product match, and a single optional clarification
question. Confidence only ever decides whether to prefill/suggest/ask —
never whether to approve or send (that's a separate, human-only gate).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

OUTCOMES = {"READY_FOR_DRAFT", "NEEDS_ONE_QUESTION", "NEEDS_DETAILED_FORM", "NO_SAFE_MATCH"}


class CustomerMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None
    confidence: float = 0.0
    match_basis: str = "NONE"  # EXACT_EMAIL|EXACT_PHONE|PAYMENT_HISTORY|USER_INPUT|NONE
    ambiguity_reason: str | None = None


class ProductMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_item_id: str | None = None
    confidence: float = 0.0
    match_basis: str = "NONE"  # PRODUCT_ID|EXACT_ALIAS|DESCRIPTION_MATCH|USER_SELECTION|NONE
    ambiguity_reason: str | None = None


class ClarificationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    field_needed: str
    answer_type: str = Field(pattern="^(SELECT|TEXT|DATE|BOOLEAN)$")
    options: list[str] = Field(default_factory=list)


class AIPrefillOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: str = Field(pattern="^(" + "|".join(OUTCOMES) + ")$")
    customer_match: CustomerMatch
    product_match: ProductMatch
    missing_critical_fields: list[str] = Field(default_factory=list)
    single_clarification_question: ClarificationQuestion | None = None
    reviewer_summary: str
    warnings: list[str] = Field(default_factory=list)
