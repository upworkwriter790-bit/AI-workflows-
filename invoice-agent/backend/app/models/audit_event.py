from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEvent(Base):
    """Append-only. Nothing in this table is ever updated or deleted by
    application code — only inserted. See app/services/audit/service.py.
    """

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    event_name: Mapped[str] = mapped_column(String(128))
    previous_state: Mapped[str | None] = mapped_column(String(64))
    new_state: Mapped[str | None] = mapped_column(String(64))
    actor_type: Mapped[str] = mapped_column(String(16))  # SYSTEM|USER|CRM|ERP|LLM
    actor_id: Mapped[str | None] = mapped_column(String(128))
    safe_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
