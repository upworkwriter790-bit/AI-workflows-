from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvoiceEditProposal(Base):
    """An AI-generated proposed edit to a draft. Never applied
    automatically — a human must call the apply endpoint, which re-checks
    `base_draft_version_number` against the draft's current version and
    rejects a stale proposal outright (rule §8 of the spec this was
    built against: "reject an apply request if proposal base version
    does not match current draft version").
    """

    __tablename__ = "invoice_edit_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    generated_invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generated_invoices.id"), index=True
    )
    base_draft_version_number: Mapped[int] = mapped_column(Integer)
    requested_by_user_id: Mapped[str] = mapped_column(String(36))
    natural_language_instruction: Mapped[str] = mapped_column(String(2000))
    structured_change_proposal_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    # PENDING|GENERATED|INVALID|APPLIED|REJECTED_BY_USER|FAILED
    proposed_change_summary: Mapped[str | None] = mapped_column(String(1000))
    validation_result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    applied_by_user_id: Mapped[str | None] = mapped_column(String(36))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by_user_id: Mapped[str | None] = mapped_column(String(36))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
