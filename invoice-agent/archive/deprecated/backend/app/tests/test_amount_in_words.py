from __future__ import annotations

from decimal import Decimal

from app.services.invoice_pdf.amount_in_words import amount_in_words


def test_amount_in_words_simple():
    assert amount_in_words(Decimal("1180.00")) == "Rupees One Thousand One Hundred Eighty Only"


def test_amount_in_words_with_paise():
    result = amount_in_words(Decimal("1180.50"))
    assert "Fifty Paise" in result
    assert result.startswith("Rupees One Thousand One Hundred Eighty")


def test_amount_in_words_lakh_and_crore():
    assert amount_in_words(Decimal("12345678.00")) == (
        "Rupees One Crore Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight Only"
    )


def test_amount_in_words_zero():
    assert amount_in_words(Decimal("0.00")) == "Rupees Zero Only"
