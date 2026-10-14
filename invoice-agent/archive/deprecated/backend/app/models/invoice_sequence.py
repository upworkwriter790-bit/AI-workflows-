from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvoiceSequence(Base):
    """One row per financial year. `last_sequence` is incremented inside a
    DB transaction with a row lock (`with_for_update()`) so concurrent
    requests never hand out the same invoice number — see
    app/services/gst/numbering.py.
    """

    __tablename__ = "invoice_sequences"

    financial_year: Mapped[str] = mapped_column(String(16), primary_key=True)  # e.g. "26-27"
    last_sequence: Mapped[int] = mapped_column(Integer, default=0)
