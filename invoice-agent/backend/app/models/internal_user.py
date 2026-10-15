from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InternalUser(Base):
    """Minimal internal-user record backing the dashboard's role-based
    authorization. A user can hold more than one role (e.g. an
    INVOICE_APPROVER who is also an INVOICE_EDITOR), stored as a
    comma-separated string — simpler than a join table for this user
    count, see `role_set`/`has_role()`.
    """

    __tablename__ = "internal_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Comma-separated, e.g. "ADMIN" or "INVOICE_EDITOR,INVOICE_APPROVER".
    # See app/core/auth.py:ROLES for the full set.
    role: Mapped[str] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def role_set(self) -> set[str]:
        return {r.strip() for r in self.role.split(",") if r.strip()}

    def has_role(self, *roles: str) -> bool:
        return bool(self.role_set & set(roles))
