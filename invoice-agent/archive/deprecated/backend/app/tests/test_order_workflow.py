from __future__ import annotations

from datetime import datetime, timezone

from pypdf import PdfReader

from app.core.config import Settings
from app.models.customer import Customer
from app.models.invoice_line_item import InvoiceLineItem
from app.models.order import Order
from app.workflows.order_workflow import process_paid_order

BILLING = {
    "line1": "1 Test St",
    "city": "Mumbai",
    "state": "Maharashtra",
    "state_code": "27",
    "postal_code": "400001",
    "country": "India",
}


def _make_settings(tmp_path, **overrides) -> Settings:
    defaults = dict(
        COMPANY_LEGAL_NAME="Test Co Pvt Ltd",
        COMPANY_REGISTERED_ADDRESS="123 Test St, Mumbai",
        SELLER_GSTIN="27AAAAA0000A1Z5",
        SELLER_STATE_NAME="Maharashtra",
        SELLER_STATE_CODE="27",
        SUPPORT_EMAIL="support@test.com",
        STORAGE_LOCAL_DIR=str(tmp_path / "storage"),
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _make_order(db_session, *, order_id: str, state_code: str = "27", state_name: str = "Maharashtra",
                 gst_rate: float = 18.00, grand_total: float = 1180.00, tax_inclusive: bool = False) -> Order:
    customer = Customer(
        crm_customer_id=f"CUS-{order_id}", legal_name="Buyer Pvt Ltd", email="buyer@example.com",
        billing_address_json=BILLING, state_name=state_name, state_code=state_code,
    )
    db_session.add(customer)
    db_session.commit()

    billing = dict(BILLING, state=state_name, state_code=state_code)
    snapshot = {
        "customer": {"name": "Buyer Pvt Ltd", "email": "buyer@example.com", "billing_address": billing},
        "items": [
            {
                "product_id": "PROD-1", "sku": "SKU-1", "name": "Widget", "description": "Widget",
                "product_type": "GOODS", "hsn_or_sac_code": "8471", "quantity": 1,
                "unit": "Nos", "unit_price": 1000.00, "discount_amount": 0, "gst_rate": gst_rate,
            }
        ],
        "pricing": {
            "tax_inclusive": tax_inclusive, "subtotal": 1000.00, "discount_total": 0,
            "tax_total": grand_total - 1000.00, "grand_total": grand_total,
        },
    }
    order = Order(
        crm_order_id=order_id, customer_id=customer.id, payment_status="paid",
        payment_reference=f"PAY-{order_id}", paid_at=datetime.now(timezone.utc),
        currency="INR", subtotal=1000.00, grand_total=grand_total,
        order_snapshot_json=snapshot, idempotency_key=f"evt-{order_id}",
    )
    db_session.add(order)
    db_session.commit()
    return order


def test_valid_order_produces_pdf_generated_invoice(db_session, tmp_path):
    settings = _make_settings(tmp_path)
    order = _make_order(db_session, order_id="ORD-1")

    outcome = process_paid_order(db_session, order.id, settings)

    assert outcome.invoice.invoice_status == "INVOICE_PDF_GENERATED"
    assert outcome.invoice.invoice_number.startswith("INV/FY")
    assert outcome.invoice.grand_total == 1180.00
    assert outcome.invoice.pdf_sha256 is not None

    line_items = db_session.query(InvoiceLineItem).filter_by(invoice_id=outcome.invoice.id).all()
    assert len(line_items) == 1
    assert float(line_items[0].line_total) == 1180.00

    import io

    stored_pdf = (tmp_path / "storage" / outcome.invoice.pdf_storage_key).read_bytes()
    reader = PdfReader(io.BytesIO(stored_pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert outcome.invoice.invoice_number in text
    assert "Test Co Pvt Ltd" in text


def test_missing_company_config_fails_validation(db_session, tmp_path):
    settings = Settings(STORAGE_LOCAL_DIR=str(tmp_path / "storage"))  # no company fields set
    order = _make_order(db_session, order_id="ORD-2")

    outcome = process_paid_order(db_session, order.id, settings)

    assert outcome.invoice.invoice_status == "VALIDATION_FAILED"
    assert outcome.invoice.invoice_number is None


def test_tax_mismatch_routes_to_manual_review(db_session, tmp_path):
    settings = _make_settings(tmp_path)
    # grand_total in the order doesn't match what GST calc will actually produce
    order = _make_order(db_session, order_id="ORD-3", grand_total=9999.00)

    outcome = process_paid_order(db_session, order.id, settings)

    assert outcome.invoice.invoice_status == "MANUAL_REVIEW_REQUIRED"
    assert outcome.invoice.invoice_number is None


def test_inter_state_order_uses_igst(db_session, tmp_path):
    settings = _make_settings(tmp_path)
    order = _make_order(db_session, order_id="ORD-4", state_code="07", state_name="Delhi")

    outcome = process_paid_order(db_session, order.id, settings)

    assert outcome.invoice.invoice_status == "INVOICE_PDF_GENERATED"
    assert float(outcome.invoice.igst_total) == 180.00
    assert float(outcome.invoice.cgst_total) == 0.00
    assert float(outcome.invoice.sgst_total) == 0.00


def test_invoice_numbers_are_sequential_across_orders(db_session, tmp_path):
    settings = _make_settings(tmp_path)
    order1 = _make_order(db_session, order_id="ORD-5")
    order2 = _make_order(db_session, order_id="ORD-6")

    outcome1 = process_paid_order(db_session, order1.id, settings)
    outcome2 = process_paid_order(db_session, order2.id, settings)

    seq1 = int(outcome1.invoice.invoice_number.rsplit("/", 1)[-1])
    seq2 = int(outcome2.invoice.invoice_number.rsplit("/", 1)[-1])
    assert seq2 == seq1 + 1


def test_missing_required_item_field_fails_validation(db_session, tmp_path):
    settings = _make_settings(tmp_path)
    order = _make_order(db_session, order_id="ORD-7")
    order.order_snapshot_json["items"][0]["hsn_or_sac_code"] = None
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(order, "order_snapshot_json")
    db_session.add(order)
    db_session.commit()

    outcome = process_paid_order(db_session, order.id, settings)

    assert outcome.invoice.invoice_status == "VALIDATION_FAILED"
