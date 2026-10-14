from __future__ import annotations

from datetime import date

from app.core.config import Settings
from app.services.gst.numbering import financial_year_label, reserve_invoice_number


def test_financial_year_label_april_start():
    assert financial_year_label(date(2026, 4, 1)) == "26-27"


def test_financial_year_label_march_is_previous_fy():
    assert financial_year_label(date(2027, 3, 31)) == "26-27"


def test_reserve_invoice_number_sequential(db_session):
    settings = Settings(INVOICE_NUMBER_FORMAT="INV/FY{fy_start}-{fy_end}/{seq:06d}")
    first = reserve_invoice_number(db_session, settings, date(2026, 10, 13))
    second = reserve_invoice_number(db_session, settings, date(2026, 10, 14))

    assert first == "INV/FY26-27/000001"
    assert second == "INV/FY26-27/000002"


def test_reserve_invoice_number_resets_per_financial_year(db_session):
    settings = Settings(INVOICE_NUMBER_FORMAT="INV/FY{fy_start}-{fy_end}/{seq:06d}")
    this_fy = reserve_invoice_number(db_session, settings, date(2027, 3, 31))
    next_fy = reserve_invoice_number(db_session, settings, date(2027, 4, 1))

    assert this_fy == "INV/FY26-27/000001"
    assert next_fy == "INV/FY27-28/000001"
