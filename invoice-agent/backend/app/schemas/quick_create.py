"""Mode B1 — Quick Create (spec: minimal payment snapshot in, AI +
trusted data resolve the rest). Deliberately small: this is the whole
point of Quick Create versus the detailed form.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuickCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_email: str | None = None
    customer_phone: str | None = None
    customer_name: str | None = None
    amount_paid: Decimal = Field(gt=0)
    payment_reference: str = Field(min_length=1, max_length=128)
    payment_date: date = Field(default_factory=date.today)
    external_reference: str | None = None
    product_text: str | None = None
    item_reference: str | None = None
    # Answers to a previous clarification round — merged in in place of
    # asking again. Keys currently understood: billing_state_name,
    # billing_state_code, product_text (a re-answer), customer_name.
    billing_state_name: str | None = None
    billing_state_code: str | None = None
    delivery_channels: list[str] = Field(default_factory=lambda: ["email"])
    notes: str | None = None

    @model_validator(mode="after")
    def require_one_contact_method(self) -> QuickCreateInput:
        if not self.customer_email and not self.customer_phone:
            raise ValueError("customer_email or customer_phone is required")
        return self
