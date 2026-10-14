from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvoiceDelivery(Base):
    __tablename__ = "invoice_deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_invoice_delivery_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoice_documents.id"), index=True)

    recipient_name: Mapped[str] = mapped_column(String(255))
    recipient_email: Mapped[str | None] = mapped_column(String(255))
    recipient_phone: Mapped[str | None] = mapped_column(String(20))
    requested_channels_json: Mapped[list] = mapped_column(JSON, default=list)  # ["email","whatsapp"]

    external_reference: Mapped[str | None] = mapped_column(String(128))
    invoice_number: Mapped[str | None] = mapped_column(String(64))

    # Preserved from the original intake request so the approval step
    # (which happens in a separate HTTP call, possibly much later) honors
    # the sender's original intent rather than guessing or hardcoding.
    attach_pdf_to_email: Mapped[bool] = mapped_column(Boolean, default=True)
    include_download_link: Mapped[bool] = mapped_column(Boolean, default=True)
    send_whatsapp_notification: Mapped[bool] = mapped_column(Boolean, default=True)

    status: Mapped[str] = mapped_column(String(32), default="RECEIVED")
    idempotency_key: Mapped[str] = mapped_column(String(255), index=True)
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
