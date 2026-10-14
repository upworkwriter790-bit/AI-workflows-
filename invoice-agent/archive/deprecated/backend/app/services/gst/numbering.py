"""Sequential, financial-year-scoped invoice numbering.

Indian FY runs April -> March. `financial_year_label(d)` for any date in
Apr 2026-Mar 2027 returns "26-27". The sequence is reserved inside a DB
transaction using `with_for_update()` (a real row lock on PostgreSQL; a
no-op on SQLite, which already serializes writers) so two concurrent
requests can never receive the same number. Once reserved, the caller is
expected to persist it on the Invoice row immediately — the spec requires
invoice numbers be immutable after ERP sync, so nothing in this module
ever decrements or reuses a number, even if the caller later fails.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.invoice_sequence import InvoiceSequence


def financial_year_label(as_of: date) -> str:
    if as_of.month >= 4:
        start_year = as_of.year
    else:
        start_year = as_of.year - 1
    end_year = start_year + 1
    return f"{start_year % 100:02d}-{end_year % 100:02d}"


def _financial_year_bounds(label: str) -> tuple[int, int]:
    start, end = label.split("-")
    return int(start), int(end)


def reserve_invoice_number(db: Session, settings: Settings, as_of: date) -> str:
    fy_label = financial_year_label(as_of)

    row = (
        db.query(InvoiceSequence)
        .filter_by(financial_year=fy_label)
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        row = InvoiceSequence(financial_year=fy_label, last_sequence=0)
        db.add(row)
        db.flush()

    row.last_sequence += 1
    seq = row.last_sequence
    db.add(row)
    db.commit()

    fy_start, fy_end = _financial_year_bounds(fy_label)
    return settings.invoice_number_format.format(fy_start=fy_start, fy_end=fy_end, seq=seq)
