from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Customer(Base):
    """A lightweight internal customer directory — not a CRM integration.
    Exists only so a returning customer's billing details can be found by
    exact email/phone match instead of re-typed every time (spec §8/§3).
    Populated by a human confirming "save to directory" after a generated
    invoice is approved; never auto-overwritten by AI output or a receipt
    upload.
    """

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name: Mapped[str] = mapped_column(String(255))
    legal_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    gstin: Mapped[str | None] = mapped_column(String(15))
    billing_address_json: Mapped[dict | None] = mapped_column(JSON)
    shipping_address_json: Mapped[dict | None] = mapped_column(JSON)
    state_name: Mapped[str | None] = mapped_column(String(64))
    state_code: Mapped[str | None] = mapped_column(String(4))
    preferred_delivery_channels_json: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(32), default="MANUAL")  # MANUAL|GENERATED_INVOICE
    verification_status: Mapped[str] = mapped_column(String(16), default="UNVERIFIED")  # UNVERIFIED|REVIEWED
    created_by_user_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
