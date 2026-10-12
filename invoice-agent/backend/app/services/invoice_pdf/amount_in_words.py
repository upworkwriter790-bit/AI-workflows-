"""Amount-in-words, Indian numbering system (thousand/lakh/crore) — the
GST invoice checklist requires "total payable amount in figures and
words" (spec §3/§10). No external dependency; small enough to keep
dependency-free and unit-test directly.
"""

from __future__ import annotations

from decimal import Decimal

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety",
]


def _two_digits(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return f"{_TENS[tens]} {_ONES[ones]}".strip()


def _three_digits(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    if hundreds and rest:
        return f"{_ONES[hundreds]} Hundred {_two_digits(rest)}"
    if hundreds:
        return f"{_ONES[hundreds]} Hundred"
    return _two_digits(rest)


def _int_to_indian_words(n: int) -> str:
    if n == 0:
        return "Zero"

    crore, remainder = divmod(n, 10_000_000)
    lakh, remainder = divmod(remainder, 100_000)
    thousand, remainder = divmod(remainder, 1_000)
    hundred = remainder

    parts: list[str] = []
    if crore:
        parts.append(f"{_three_digits(crore)} Crore")
    if lakh:
        parts.append(f"{_three_digits(lakh)} Lakh")
    if thousand:
        parts.append(f"{_three_digits(thousand)} Thousand")
    if hundred:
        parts.append(_three_digits(hundred))

    return " ".join(parts)


def amount_in_words(amount: Decimal, currency_label: str = "Rupees") -> str:
    amount = amount.copy_abs()
    rupees = int(amount)
    paise = int((amount - rupees) * 100)

    words = f"{currency_label} {_int_to_indian_words(rupees)} Only"
    if paise:
        words = f"{currency_label} {_int_to_indian_words(rupees)} and {_int_to_indian_words(paise)} Paise Only"
    return words
