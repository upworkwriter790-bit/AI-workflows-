"""Request schema for POST /api/v1/generated-invoice-deliveries (spec §4).

`extra="forbid"` everywhere is deliberate: it is the mechanism that
enforces "do not accept raw card numbers, bank-account numbers, UPI PINs,
CVVs, or payment credentials" — any field not explicitly listed here
(including those) is rejected at the schema layer before anything touches
a database or a log line.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ALLOWED_CHANNELS = {"email", "whatsapp"}


class GeneratedInvoiceAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line1: str
    line2: str | None = None
    city: str
    district: str | None = None
    state: str
    state_code: str = Field(min_length=1, max_length=4)
    postal_code: str
    country: str = "India"


class GeneratedInvoiceShippingAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    same_as_billing: bool = False
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    state_code: str | None = None
    postal_code: str | None = None
    country: str = "India"


class GeneratedInvoiceRecipient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = None
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    billing_address: GeneratedInvoiceAddress
    shipping_address: GeneratedInvoiceShippingAddress | None = None


class PaymentOrOrderDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_reference: str = Field(min_length=1)
    payment_date: date
    currency: str = "INR"
    tax_inclusive: bool
    subtotal: Decimal
    discount_total: Decimal = Decimal(0)
    tax_total: Decimal
    grand_total: Decimal
    payment_status: str
    payment_method_label: str | None = None

    @field_validator("payment_status")
    @classmethod
    def payment_must_already_be_paid(cls, v: str) -> str:
        if v != "PAID":
            raise ValueError("payment_status must be 'PAID' — this workflow starts after payment")
        return v

    @field_validator("subtotal", "discount_total", "tax_total", "grand_total")
    @classmethod
    def amounts_must_not_be_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("amounts must not be negative")
        return v


class GeneratedInvoiceLineItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_reference: str | None = None
    description: str = Field(min_length=1, max_length=500)
    product_type: str = Field(pattern="^(GOODS|SERVICE)$")
    hsn_or_sac_code: str = Field(min_length=1, max_length=16)
    quantity: Decimal
    unit: str
    unit_price: Decimal
    discount_amount: Decimal = Decimal(0)
    gst_rate: Decimal
    configured_tax_category: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v

    @field_validator("unit_price", "discount_amount")
    @classmethod
    def amount_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("amount must be greater than or equal to 0")
        return v

    @field_validator("gst_rate")
    @classmethod
    def gst_rate_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("gst_rate must not be negative")
        return v


class GeneratedInvoiceDeliveryOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_channels: list[str] = Field(min_length=1)
    attach_pdf_to_email: bool = True
    include_secure_download_link: bool = True
    send_whatsapp_notification: bool = True

    @field_validator("requested_channels")
    @classmethod
    def channels_known(cls, v: list[str]) -> list[str]:
        normalized = [c.strip().lower() for c in v if c.strip()]
        if not normalized:
            raise ValueError("at least one delivery channel is required")
        unknown = set(normalized) - ALLOWED_CHANNELS
        if unknown:
            raise ValueError(f"unknown channel(s): {sorted(unknown)}")
        return normalized


class GeneratedInvoiceDeliveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=255)
    external_reference: str = Field(min_length=1, max_length=128)
    recipient: GeneratedInvoiceRecipient
    payment_or_order_details: PaymentOrOrderDetails
    items: list[GeneratedInvoiceLineItemRequest] = Field(min_length=1)
    delivery: GeneratedInvoiceDeliveryOptions
    notes: str | None = None

    def require_channel_contact_info(self) -> list[str]:
        errors = []
        if "email" in self.delivery.requested_channels and not self.recipient.email:
            errors.append("recipient.email is required when email is a requested channel")
        if "whatsapp" in self.delivery.requested_channels and not self.recipient.phone:
            errors.append("recipient.phone is required when whatsapp is a requested channel")
        return errors
