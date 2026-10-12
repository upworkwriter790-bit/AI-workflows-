from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)

    llm_recommendation: Mapped[str | None] = mapped_column(String(32))  # ACCEPT|HOLD_FOR_REVIEW|REJECT
    final_decision: Mapped[str | None] = mapped_column(String(32))

    deterministic_rules_result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    reasons_json: Mapped[dict] = mapped_column(JSON, default=dict)

    decided_by: Mapped[str] = mapped_column(String(64))  # SYSTEM | <user_id>
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
