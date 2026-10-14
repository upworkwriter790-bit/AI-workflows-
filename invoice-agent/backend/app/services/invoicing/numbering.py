"""Transaction-safe, India-financial-year-scoped invoice numbering for
Method B (spec §8). `with_for_update()` gives a real row lock on
PostgreSQL; on SQLite it's a no-op but SQLite already serializes writers,
so concurrent requests still can't receive the same number.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.invoice_number_sequence import InvoiceNumberSequence


def financial_year_label(as_of: date, fy_start_month: int = 4) -> str:
    if as_of.month >= fy_start_month:
        start_year = as_of.year
    else:
        start_year = as_of.year - 1
    end_year = start_year + 1
    return f"{start_year % 100:02d}-{end_year % 100:02d}"


def reserve_invoice_number(db: Session, settings: Settings, as_of: date) -> str:
    fy_label = financial_year_label(as_of, settings.financial_year_start_month)

    row = (
        db.query(InvoiceNumberSequence)
        .filter_by(financial_year=fy_label)
        .with_for_update()
        .one_or_none()
    )
    if row is None:
        row = InvoiceNumberSequence(financial_year=fy_label, last_sequence=0)
        db.add(row)
        db.flush()

    row.last_sequence += 1
    seq = row.last_sequence
    db.add(row)
    db.commit()

    fy_start, fy_end = fy_label.split("-")
    return settings.invoice_number_format.format(
        prefix=settings.invoice_prefix,
        fy_start_short=fy_start,
        fy_end_short=fy_end,
        sequence=str(seq).zfill(settings.invoice_sequence_padding),
    )
