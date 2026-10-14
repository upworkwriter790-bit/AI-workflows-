from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvoiceDocument(Base):
    """The already-created invoice PDF this system stores and delivers.
    Never generated, edited, or interpreted here — only stored.
    """

    __tablename__ = "invoice_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename: Mapped[str] = mapped_column(String(512))
    sanitized_filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    uploaded_by_user_id: Mapped[str | None] = mapped_column(String(36))
    external_reference: Mapped[str | None] = mapped_column(String(128))
    invoice_number: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32))  # INTERNAL_UPLOAD|API|EMAIL_INTAKE
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
