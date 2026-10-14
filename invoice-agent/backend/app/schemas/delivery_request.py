"""Validation for the non-file fields of POST /api/v1/invoice-deliveries
(§6). The file itself is validated separately in
app/services/file_validation.py since it arrives as raw bytes, not JSON.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

ALLOWED_CHANNELS = {"email", "whatsapp"}
ALLOWED_SOURCES = {"INTERNAL_UPLOAD", "API", "EMAIL_INTAKE"}


class InvoiceDeliveryRequestFields(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=255)
    recipient_email: EmailStr | None = None
    recipient_phone: str | None = None
    requested_channels: list[str]
    idempotency_key: str = Field(min_length=1, max_length=255)

    external_reference: str | None = None
    invoice_number: str | None = None
    source: str = "INTERNAL_UPLOAD"
    notes: str | None = None
    attach_pdf_to_email: bool = True
    include_download_link: bool = True
    send_whatsapp_notification: bool = True

    @field_validator("requested_channels")
    @classmethod
    def channels_must_be_known_and_nonempty(cls, v: list[str]) -> list[str]:
        normalized = [c.strip().lower() for c in v if c.strip()]
        if not normalized:
            raise ValueError("at least one delivery channel is required")
        unknown = set(normalized) - ALLOWED_CHANNELS
        if unknown:
            raise ValueError(f"unknown channel(s): {sorted(unknown)}")
        return normalized

    @field_validator("source")
    @classmethod
    def source_must_be_known(cls, v: str) -> str:
        if v not in ALLOWED_SOURCES:
            raise ValueError(f"source must be one of {sorted(ALLOWED_SOURCES)}")
        return v

    def require_channel_contact_info(self) -> list[str]:
        """Returns a list of validation error strings (empty = ok)."""
        errors = []
        if "email" in self.requested_channels and not self.recipient_email:
            errors.append("recipient_email is required when email is a requested channel")
        if "whatsapp" in self.requested_channels and not self.recipient_phone:
            errors.append("recipient_phone is required when whatsapp is a requested channel")
        return errors
