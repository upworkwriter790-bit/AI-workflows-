from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_number: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    invoice_type: Mapped[str] = mapped_column(String(32))  # SALES_INVOICE | RECEIVED_DOCUMENT

    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("orders.id"))
    customer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("customers.id"))

    issuer_name: Mapped[str | None] = mapped_column(String(255))
    issuer_gstin: Mapped[str | None] = mapped_column(String(15))
    recipient_name: Mapped[str | None] = mapped_column(String(255))
    recipient_gstin: Mapped[str | None] = mapped_column(String(15))

    invoice_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    discount_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    taxable_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    cgst_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    sgst_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    igst_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    cess_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    grand_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    place_of_supply: Mapped[str | None] = mapped_column(String(64))
    reverse_charge_applicable: Mapped[bool] = mapped_column(Boolean, default=False)

    invoice_status: Mapped[str] = mapped_column(String(48), default="PAID_ORDER_RECEIVED")
    template_version: Mapped[str | None] = mapped_column(String(16))
    pdf_storage_key: Mapped[str | None] = mapped_column(String(512))
    pdf_sha256: Mapped[str | None] = mapped_column(String(64))

    erp_invoice_id: Mapped[str | None] = mapped_column(String(128), index=True)
    crm_invoice_reference: Mapped[str | None] = mapped_column(String(128))

    email_status: Mapped[str | None] = mapped_column(String(32))  # sent|delivered|bounced|failed
    email_message_id: Mapped[str | None] = mapped_column(String(255))

    operations_notification_status: Mapped[str | None] = mapped_column(String(32))
    product_access_status: Mapped[str | None] = mapped_column(String(32))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
