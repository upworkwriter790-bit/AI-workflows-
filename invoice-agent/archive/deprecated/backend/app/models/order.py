from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crm_order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"))
    payment_status: Mapped[str] = mapped_column(String(32))
    payment_reference: Mapped[str | None] = mapped_column(String(128))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    discount_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    grand_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    order_snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
