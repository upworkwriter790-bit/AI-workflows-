from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeneratedInvoiceLineItem(Base):
    __tablename__ = "generated_invoice_line_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    generated_invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generated_invoices.id"), index=True
    )
    line_number: Mapped[int] = mapped_column(Integer)
    item_reference: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(500))
    product_type: Mapped[str] = mapped_column(String(16))  # GOODS | SERVICE
    hsn_or_sac_code: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[str] = mapped_column(Numeric(14, 3))
    unit: Mapped[str] = mapped_column(String(16))
    unit_price: Mapped[str] = mapped_column(Numeric(14, 2))
    discount_amount: Mapped[str] = mapped_column(Numeric(14, 2), default=0)
    taxable_value: Mapped[str] = mapped_column(Numeric(14, 2))
    gst_rate: Mapped[str] = mapped_column(Numeric(5, 2))
    cgst_amount: Mapped[str] = mapped_column(Numeric(14, 2), default=0)
    sgst_amount: Mapped[str] = mapped_column(Numeric(14, 2), default=0)
    igst_amount: Mapped[str] = mapped_column(Numeric(14, 2), default=0)
    cess_amount: Mapped[str] = mapped_column(Numeric(14, 2), default=0)
    line_total: Mapped[str] = mapped_column(Numeric(14, 2))
