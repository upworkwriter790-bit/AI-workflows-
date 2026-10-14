from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductCatalogItem(Base):
    """The product/tax catalog a Method-B caller must reference rather
    than invent HSN/SAC codes and GST rates per invoice line. Editable
    only through an ADMIN-gated path (see app/api/product_catalog.py) —
    every change to this table should be approved by the company's CA/GST
    professional before going live, per the project's own configuration
    note (see docs/delivery-rules.md).
    """

    __tablename__ = "product_catalog_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    internal_reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_description: Mapped[str] = mapped_column(String(500))
    product_type: Mapped[str] = mapped_column(String(16))  # GOODS | SERVICE
    hsn_or_sac_code: Mapped[str] = mapped_column(String(16))
    unit: Mapped[str] = mapped_column(String(16))
    unit_price: Mapped[str] = mapped_column(Numeric(14, 2))
    gst_rate: Mapped[str] = mapped_column(Numeric(5, 2))
    tax_category: Mapped[str | None] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
