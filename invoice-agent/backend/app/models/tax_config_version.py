from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaxConfigVersion(Base):
    """An audited, versioned snapshot of the tax-calculation configuration
    (rounding mode, tolerance, GST split rule, etc). Only an ADMIN may
    create a new version (see app/api/tax_config.py); the calculator
    always reads the highest `version` row marked `is_active`. Rows are
    never edited in place — a change creates a new version, so the full
    history of what rules applied when is preserved.
    """

    __tablename__ = "tax_config_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    version: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    config_json: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
