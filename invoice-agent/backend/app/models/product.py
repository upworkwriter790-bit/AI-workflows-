from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crm_product_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    sku: Mapped[str | None] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(2000))
    hsn_or_sac_code: Mapped[str | None] = mapped_column(String(16))
    product_type: Mapped[str] = mapped_column(String(16))  # GOODS | SERVICE
    unit: Mapped[str | None] = mapped_column(String(16))
    default_gst_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
