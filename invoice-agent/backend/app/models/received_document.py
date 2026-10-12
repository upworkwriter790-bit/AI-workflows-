from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReceivedDocument(Base):
    __tablename__ = "received_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type: Mapped[str] = mapped_column(String(32))  # PORTAL|EMAIL|CRM|API|INTERNAL_UPLOAD
    source_reference: Mapped[str | None] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    storage_key: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    issuer_email: Mapped[str | None] = mapped_column(String(255))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    extraction_status: Mapped[str] = mapped_column(String(32), default="DOCUMENT_RECEIVED")
    extraction_json: Mapped[dict | None] = mapped_column(JSON)
    extracted_confidence_json: Mapped[dict | None] = mapped_column(JSON)

    matched_invoice_id: Mapped[str | None] = mapped_column(String(36))
    decision_status: Mapped[str | None] = mapped_column(String(32))  # ACCEPT|HOLD_FOR_REVIEW|REJECT
    decision_reason_json: Mapped[dict | None] = mapped_column(JSON)
