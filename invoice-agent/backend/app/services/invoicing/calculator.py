"""Deterministic, decimal-safe GST calculation for Method B (generated
invoices). No LLM is involved anywhere in this module — every number
comes from configured rates and plain Decimal arithmetic (spec §7).

Every call's inputs and outputs are meant to be captured verbatim into
`GeneratedInvoice.calculation_snapshot_json` by the caller (the workflow),
so a later audit can see exactly what was computed and why — this module
itself does not persist anything, it only computes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")

_ROUNDING_MODES = {
    "HALF_UP": ROUND_HALF_UP,
}


def _round(value: Decimal, rounding_mode: str) -> Decimal:
    mode = _ROUNDING_MODES.get(rounding_mode, ROUND_HALF_UP)
    return value.quantize(TWO_PLACES, rounding=mode)


@dataclass
class LineItemInput:
    description: str
    product_type: str
    hsn_or_sac_code: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    discount_amount: Decimal
    gst_rate: Decimal
    item_reference: str | None = None


@dataclass
class LineItemResult:
    description: str
    product_type: str
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
    item_reference: str | None = None


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
    tax_total: Decimal
    grand_total: Decimal
    line_items: list[LineItemResult] = field(default_factory=list)

    def snapshot(self) -> dict:
        """A JSON-serializable record of the computed result, for
        `calculation_snapshot_json`.
        """
        return {
            "is_inter_state": self.is_inter_state,
            "place_of_supply_state": self.place_of_supply_state,
            "subtotal": str(self.subtotal),
            "discount_total": str(self.discount_total),
            "taxable_total": str(self.taxable_total),
            "cgst_total": str(self.cgst_total),
            "sgst_total": str(self.sgst_total),
            "igst_total": str(self.igst_total),
            "cess_total": str(self.cess_total),
            "tax_total": str(self.tax_total),
            "grand_total": str(self.grand_total),
            "line_items": [
                {
                    "description": li.description,
                    "hsn_or_sac_code": li.hsn_or_sac_code,
                    "quantity": str(li.quantity),
                    "unit_price": str(li.unit_price),
                    "discount_amount": str(li.discount_amount),
                    "taxable_value": str(li.taxable_value),
                    "gst_rate": str(li.gst_rate),
                    "cgst_amount": str(li.cgst_amount),
                    "sgst_amount": str(li.sgst_amount),
                    "igst_amount": str(li.igst_amount),
                    "line_total": str(li.line_total),
                }
                for li in self.line_items
            ],
        }


def calculate_invoice_tax(
    *,
    line_items: list[LineItemInput],
    seller_state_code: str,
    recipient_state_code: str,
    place_of_supply_state_name: str,
    tax_inclusive: bool,
    rounding_mode: str = "HALF_UP",
) -> GSTCalculationResult:
    is_inter_state = seller_state_code.strip() != recipient_state_code.strip()

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
            taxable_value = _round(
                net_of_discount / (Decimal(1) + item.gst_rate / Decimal(100)), rounding_mode
            )
            tax_amount = _round(net_of_discount - taxable_value, rounding_mode)
            line_total = _round(net_of_discount, rounding_mode)
        else:
            taxable_value = _round(net_of_discount, rounding_mode)
            tax_amount = _round(taxable_value * item.gst_rate / Decimal(100), rounding_mode)
            line_total = _round(taxable_value + tax_amount, rounding_mode)

        if is_inter_state:
            cgst_amount = Decimal(0)
            sgst_amount = Decimal(0)
            igst_amount = tax_amount
        else:
            cgst_amount = _round(tax_amount / 2, rounding_mode)
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
                product_type=item.product_type,
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
                item_reference=item.item_reference,
            )
        )

    tax_total = cgst_total + sgst_total + igst_total

    return GSTCalculationResult(
        is_inter_state=is_inter_state,
        place_of_supply_state=place_of_supply_state_name,
        subtotal=_round(subtotal, rounding_mode),
        discount_total=_round(discount_total, rounding_mode),
        taxable_total=_round(taxable_total, rounding_mode),
        cgst_total=_round(cgst_total, rounding_mode),
        sgst_total=_round(sgst_total, rounding_mode),
        igst_total=_round(igst_total, rounding_mode),
        cess_total=Decimal(0),
        tax_total=_round(tax_total, rounding_mode),
        grand_total=_round(grand_total, rounding_mode),
        line_items=results,
    )


def amounts_match_within_tolerance(computed: Decimal, stated: Decimal, tolerance: Decimal) -> bool:
    return abs(computed - stated) <= tolerance
