from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    delivery_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoice_deliveries.id"), index=True)
    channel: Mapped[str] = mapped_column(String(16))  # EMAIL|WHATSAPP
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    is_resend: Mapped[bool] = mapped_column(default=False)
    resend_reason: Mapped[str | None] = mapped_column(String(500))
    resend_requested_by_user_id: Mapped[str | None] = mapped_column(String(36))

    status: Mapped[str] = mapped_column(String(16), default="QUEUED")
    # QUEUED|SENDING|SENT|DELIVERED|READ|BOUNCED|FAILED|RETRYING

    provider: Mapped[str | None] = mapped_column(String(32))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    provider_response_safe_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message_safe: Mapped[str | None] = mapped_column(String(500))

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
