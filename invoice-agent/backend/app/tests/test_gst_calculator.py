from __future__ import annotations

from decimal import Decimal

from app.services.gst.calculator import (
    LineItemInput,
    amounts_match_within_tolerance,
    calculate_invoice_tax,
)


def test_intra_state_splits_cgst_sgst_evenly():
    result = calculate_invoice_tax(
        line_items=[
            LineItemInput(
                description="Widget", hsn_or_sac_code="8471", quantity=Decimal(1),
                unit="Nos", unit_price=Decimal("1000.00"), discount_amount=Decimal(0),
                gst_rate=Decimal("18.00"),
            )
        ],
        seller_state_code="27", customer_state_code="27", customer_state_name="Maharashtra",
        tax_inclusive=False,
    )
    assert result.is_inter_state is False
    assert result.cgst_total == Decimal("90.00")
    assert result.sgst_total == Decimal("90.00")
    assert result.igst_total == Decimal("0.00")
    assert result.grand_total == Decimal("1180.00")


def test_inter_state_uses_igst_only():
    result = calculate_invoice_tax(
        line_items=[
            LineItemInput(
                description="Widget", hsn_or_sac_code="8471", quantity=Decimal(1),
                unit="Nos", unit_price=Decimal("1000.00"), discount_amount=Decimal(0),
                gst_rate=Decimal("18.00"),
            )
        ],
        seller_state_code="27", customer_state_code="07", customer_state_name="Delhi",
        tax_inclusive=False,
    )
    assert result.is_inter_state is True
    assert result.cgst_total == Decimal("0.00")
    assert result.sgst_total == Decimal("0.00")
    assert result.igst_total == Decimal("180.00")
    assert result.grand_total == Decimal("1180.00")


def test_tax_inclusive_backs_out_taxable_value():
    result = calculate_invoice_tax(
        line_items=[
            LineItemInput(
                description="Widget", hsn_or_sac_code="8471", quantity=Decimal(1),
                unit="Nos", unit_price=Decimal("1180.00"), discount_amount=Decimal(0),
                gst_rate=Decimal("18.00"),
            )
        ],
        seller_state_code="27", customer_state_code="27", customer_state_name="Maharashtra",
        tax_inclusive=True,
    )
    assert result.taxable_total == Decimal("1000.00")
    assert result.grand_total == Decimal("1180.00")


def test_discount_reduces_taxable_value():
    result = calculate_invoice_tax(
        line_items=[
            LineItemInput(
                description="Widget", hsn_or_sac_code="8471", quantity=Decimal(2),
                unit="Nos", unit_price=Decimal("500.00"), discount_amount=Decimal("100.00"),
                gst_rate=Decimal("18.00"),
            )
        ],
        seller_state_code="27", customer_state_code="27", customer_state_name="Maharashtra",
        tax_inclusive=False,
    )
    # gross 1000, discount 100 -> taxable 900, tax 162, total 1062
    assert result.taxable_total == Decimal("900.00")
    assert result.grand_total == Decimal("1062.00")


def test_amounts_match_within_tolerance():
    assert amounts_match_within_tolerance(Decimal("1180.00"), Decimal("1180.00"), Decimal("0.01")) is True
    assert amounts_match_within_tolerance(Decimal("1180.00"), Decimal("1180.005"), Decimal("0.01")) is True
    assert amounts_match_within_tolerance(Decimal("1180.00"), Decimal("1181.00"), Decimal("0.01")) is False
