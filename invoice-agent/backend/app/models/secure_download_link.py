from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SecureDownloadLink(Base):
    """Only `token_hash` is stored — the opaque token itself is handed to
    the caller once and never persisted in recoverable form. See
    app/services/secure_links/service.py.
    """

    __tablename__ = "secure_download_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoice_documents.id"), index=True)
    delivery_id: Mapped[str] = mapped_column(String(36), ForeignKey("invoice_deliveries.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_downloads: Mapped[int] = mapped_column(Integer)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
