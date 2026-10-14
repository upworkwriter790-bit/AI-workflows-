from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoices.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("products.id"))
    external_product_reference: Mapped[str | None] = mapped_column(String(128))

    description: Mapped[str] = mapped_column(String(2000))
    hsn_or_sac_code: Mapped[str | None] = mapped_column(String(16))
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=1)
    unit: Mapped[str | None] = mapped_column(String(16))
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    taxable_value: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    gst_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    cgst_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    sgst_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    igst_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    cess_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
