from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    crm_customer_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    gstin: Mapped[str | None] = mapped_column(String(15))
    billing_address_json: Mapped[dict] = mapped_column(JSON, default=dict)
    shipping_address_json: Mapped[dict] = mapped_column(JSON, default=dict)
    state_name: Mapped[str | None] = mapped_column(String(64))
    state_code: Mapped[str | None] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
