"""Deterministic GST calculation. The LLM never touches this file's output
— every number here comes from configured rates and plain arithmetic.

Rules (spec §10):
- Same state (seller state code == customer/place-of-supply state code):
  CGST + SGST, each half of the line's gst_rate.
- Different state: IGST at the full gst_rate.
- tax_inclusive=True: the line's unit_price * quantity (minus discount) is
  treated as inclusive of tax; back out the taxable value and tax amounts.
- tax_inclusive=False: unit_price * quantity (minus discount) IS the
  taxable value; tax is added on top.
- The computed grand_total is compared against the order's own stated
  grand_total within `tolerance`; a mismatch beyond tolerance is the
  caller's signal to route to MANUAL_REVIEW_REQUIRED — this module never
  silently accepts or silently "corrects" a mismatch, it only reports it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class LineItemInput:
    description: str
    hsn_or_sac_code: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    discount_amount: Decimal
    gst_rate: Decimal
    product_id: str | None = None
    sku: str | None = None


@dataclass
class LineItemResult:
    description: str
    hsn_or_sac_code: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    discount_amount: Decimal
    taxable_value: Decimal
    gst_rate: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    line_total: Decimal
    product_id: str | None = None
    sku: str | None = None


@dataclass
class GSTCalculationResult:
    is_inter_state: bool
    place_of_supply_state: str
    subtotal: Decimal
    discount_total: Decimal
    taxable_total: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    cess_total: Decimal
    grand_total: Decimal
    line_items: list[LineItemResult] = field(default_factory=list)


def calculate_invoice_tax(
    *,
    line_items: list[LineItemInput],
    seller_state_code: str,
    customer_state_code: str,
    customer_state_name: str,
    tax_inclusive: bool,
) -> GSTCalculationResult:
    is_inter_state = seller_state_code.strip() != customer_state_code.strip()

    results: list[LineItemResult] = []
    subtotal = Decimal(0)
    discount_total = Decimal(0)
    taxable_total = Decimal(0)
    cgst_total = Decimal(0)
    sgst_total = Decimal(0)
    igst_total = Decimal(0)
    grand_total = Decimal(0)

    for item in line_items:
        gross = item.unit_price * item.quantity
        subtotal += gross
        discount_total += item.discount_amount
        net_of_discount = gross - item.discount_amount

        if tax_inclusive:
            taxable_value = _round(net_of_discount / (Decimal(1) + item.gst_rate / Decimal(100)))
            tax_amount = _round(net_of_discount - taxable_value)
            line_total = _round(net_of_discount)
        else:
            taxable_value = _round(net_of_discount)
            tax_amount = _round(taxable_value * item.gst_rate / Decimal(100))
            line_total = _round(taxable_value + tax_amount)

        if is_inter_state:
            cgst_amount = Decimal(0)
            sgst_amount = Decimal(0)
            igst_amount = tax_amount
        else:
            cgst_amount = _round(tax_amount / 2)
            sgst_amount = tax_amount - cgst_amount
            igst_amount = Decimal(0)

        taxable_total += taxable_value
        cgst_total += cgst_amount
        sgst_total += sgst_amount
        igst_total += igst_amount
        grand_total += line_total

        results.append(
            LineItemResult(
                description=item.description,
                hsn_or_sac_code=item.hsn_or_sac_code,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                discount_amount=item.discount_amount,
                taxable_value=taxable_value,
                gst_rate=item.gst_rate,
                cgst_amount=cgst_amount,
                sgst_amount=sgst_amount,
                igst_amount=igst_amount,
                cess_amount=Decimal(0),
                line_total=line_total,
                product_id=item.product_id,
                sku=item.sku,
            )
        )

    return GSTCalculationResult(
        is_inter_state=is_inter_state,
        place_of_supply_state=customer_state_name,
        subtotal=_round(subtotal),
        discount_total=_round(discount_total),
        taxable_total=_round(taxable_total),
        cgst_total=_round(cgst_total),
        sgst_total=_round(sgst_total),
        igst_total=_round(igst_total),
        cess_total=Decimal(0),
        grand_total=_round(grand_total),
        line_items=results,
    )


def amounts_match_within_tolerance(computed: Decimal, stated: Decimal, tolerance: Decimal) -> bool:
    return abs(computed - stated) <= tolerance
