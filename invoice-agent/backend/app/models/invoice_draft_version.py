from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvoiceDraftVersion(Base):
    """Append-only, immutable snapshot of a GeneratedInvoice draft at one
    point in time. Never mutate an existing row — every edit (manual or
    an applied AI proposal) inserts a new version and flips `is_current`
    on the previous one to False. `generated_invoice_id` + `created_at`
    (not an updated-in-place row) is the audit trail of how the draft
    reached its approved state.
    """

    __tablename__ = "invoice_draft_versions"
    __table_args__ = (
        UniqueConstraint("generated_invoice_id", "version_number", name="uq_draft_version_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    generated_invoice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generated_invoices.id"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    parent_version_number: Mapped[int | None] = mapped_column(Integer)
    created_by_type: Mapped[str] = mapped_column(String(24))  # SYSTEM|USER|AI_PROPOSAL_APPLIED
    created_by_user_id: Mapped[str | None] = mapped_column(String(36))
    creation_reason: Mapped[str] = mapped_column(String(32))
    # INITIAL_GENERATION|MANUAL_EDIT|AI_PROPOSAL_APPLIED|FINAL_APPROVAL_SNAPSHOT

    invoice_data_snapshot_json: Mapped[dict] = mapped_column(JSON)
    line_items_snapshot_json: Mapped[list] = mapped_column(JSON)
    calculation_snapshot_json: Mapped[dict] = mapped_column(JSON)
    validation_result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    template_version: Mapped[str | None] = mapped_column(String(16))
    draft_pdf_storage_key: Mapped[str | None] = mapped_column(String(500))
    draft_pdf_sha256: Mapped[str | None] = mapped_column(String(64))
    change_summary: Mapped[str | None] = mapped_column(String(1000))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
