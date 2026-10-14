"""Pydantic models for the CRM `order.paid` webhook — exact shape from
spec §8. Validation here is what produces the 400 response; nothing past
this layer re-interprets a missing/malformed field as a default value.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, field_validator


class Address(BaseModel):
    line1: str
    line2: str | None = None
    city: str
    district: str | None = None
    state: str
    state_code: str
    postal_code: str
    country: str = "India"


class WebhookCustomer(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    gstin: str | None = None
    billing_address: Address
    shipping_address: Address | None = None


class WebhookLineItem(BaseModel):
    product_id: str
    sku: str | None = None
    name: str
    description: str | None = None
    product_type: str = Field(pattern="^(GOODS|SERVICE)$")
    hsn_or_sac_code: str
    quantity: Decimal = Decimal(1)
    unit: str = "Nos"
    unit_price: Decimal
    discount_amount: Decimal = Decimal(0)
    gst_rate: Decimal

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v


class WebhookPricing(BaseModel):
    tax_inclusive: bool
    subtotal: Decimal
    discount_total: Decimal = Decimal(0)
    tax_total: Decimal
    grand_total: Decimal


class OrderPaidWebhookPayload(BaseModel):
    event_id: str
    event_type: str = Field(pattern="^order\\.paid$")
    occurred_at: datetime
    order_id: str
    customer_id: str
    payment_status: str = Field(pattern="^paid$")
    payment_reference: str
    currency: str = "INR"
    customer: WebhookCustomer
    items: list[WebhookLineItem] = Field(min_length=1)
    pricing: WebhookPricing
