from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeneratedInvoice(Base):
    """A Method-B invoice. Sits as an editable `DRAFT` (no invoice number,
    no PDF, no InvoiceDocument/InvoiceDelivery yet) until an authorized
    user calls the approve endpoint. Immutable once `generated_at` is set
    (spec §6) — application code must never update invoice_number,
    calculation_snapshot_json, the financial columns, or pdf_sha256 after
    that point, only create a separate credit-note/replacement record in
    a future design.
    """

    __tablename__ = "generated_invoices"
    __table_args__ = (
        UniqueConstraint(
            "external_reference", "payment_reference", name="uq_generated_invoice_refs"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("invoice_documents.id"), unique=True
    )
    external_reference: Mapped[str] = mapped_column(String(128), index=True)
    payment_reference: Mapped[str] = mapped_column(String(128), index=True)
    payment_date: Mapped[date] = mapped_column(Date)
    payment_status: Mapped[str] = mapped_column(String(32))

    invoice_number: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    invoice_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    tax_inclusive: Mapped[bool] = mapped_column(Boolean)

    seller_legal_name: Mapped[str] = mapped_column(String(255))
    seller_registered_address: Mapped[str] = mapped_column(String(1000))
    seller_gstin: Mapped[str] = mapped_column(String(15))
    seller_state_name: Mapped[str] = mapped_column(String(64))
    seller_state_code: Mapped[str] = mapped_column(String(4))

    recipient_name: Mapped[str] = mapped_column(String(255))
    recipient_email: Mapped[str | None] = mapped_column(String(255))
    recipient_phone: Mapped[str | None] = mapped_column(String(20))
    recipient_gstin: Mapped[str | None] = mapped_column(String(15))
    billing_address_json: Mapped[dict] = mapped_column(JSON)
    shipping_address_json: Mapped[dict | None] = mapped_column(JSON)
    place_of_supply: Mapped[str] = mapped_column(String(64))

    subtotal: Mapped[str] = mapped_column(Numeric(14, 2))
    discount_total: Mapped[str] = mapped_column(Numeric(14, 2), default=0)
    taxable_total: Mapped[str] = mapped_column(Numeric(14, 2))
    cgst_total: Mapped[str] = mapped_column(Numeric(14, 2), default=0)
    sgst_total: Mapped[str] = mapped_column(Numeric(14, 2), default=0)
    igst_total: Mapped[str] = mapped_column(Numeric(14, 2), default=0)
    cess_total: Mapped[str] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[str] = mapped_column(Numeric(14, 2))
    grand_total: Mapped[str] = mapped_column(Numeric(14, 2))
    amount_in_words: Mapped[str] = mapped_column(String(500))

    template_version: Mapped[str | None] = mapped_column(String(16))
    calculation_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    pdf_sha256: Mapped[str | None] = mapped_column(String(64))

    # Delivery intent, preserved from intake so the approve step (a
    # separate call, after a human has reviewed/edited the draft) can
    # act on it without the caller resubmitting anything.
    requested_channels_json: Mapped[list] = mapped_column(JSON, default=list)
    attach_pdf_to_email: Mapped[bool] = mapped_column(Boolean, default=True)
    include_download_link: Mapped[bool] = mapped_column(Boolean, default=True)
    send_whatsapp_notification: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(String(2000))

    status: Mapped[str] = mapped_column(String(48), default="REQUEST_RECEIVED")
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36))
    approved_by_user_id: Mapped[str | None] = mapped_column(String(36))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
