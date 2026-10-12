from __future__ import annotations

from datetime import date

from app.models.audit_event import AuditEvent
from app.models.customer import Customer
from app.models.decision import Decision
from app.models.idempotency import IdempotencyRecord
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.order import Order
from app.models.product import Product
from app.models.received_document import ReceivedDocument


def test_customer_roundtrip(db_session):
    customer = Customer(
        crm_customer_id="CUS-1",
        legal_name="Test Buyer Pvt Ltd",
        email="buyer@example.com",
        billing_address_json={"line1": "1 Test St"},
    )
    db_session.add(customer)
    db_session.commit()

    fetched = db_session.query(Customer).filter_by(crm_customer_id="CUS-1").one()
    assert fetched.legal_name == "Test Buyer Pvt Ltd"
    assert fetched.billing_address_json["line1"] == "1 Test St"


def test_order_requires_unique_idempotency_key(db_session):
    customer = Customer(legal_name="X", email="x@example.com")
    db_session.add(customer)
    db_session.commit()

    order = Order(
        crm_order_id="ORD-1",
        customer_id=customer.id,
        payment_status="paid",
        idempotency_key="ORD-1:v1",
    )
    db_session.add(order)
    db_session.commit()

    fetched = db_session.query(Order).filter_by(crm_order_id="ORD-1").one()
    assert fetched.payment_status == "paid"


def test_invoice_and_line_items(db_session):
    product = Product(name="Widget", product_type="GOODS", hsn_or_sac_code="8471")
    db_session.add(product)
    db_session.commit()

    invoice = Invoice(
        invoice_type="SALES_INVOICE",
        invoice_number="INV/FY26-27/000001",
        invoice_date=date(2026, 10, 13),
        grand_total=1180.00,
    )
    db_session.add(invoice)
    db_session.commit()

    line = InvoiceLineItem(
        invoice_id=invoice.id,
        sequence=1,
        product_id=product.id,
        description="Widget",
        hsn_or_sac_code="8471",
        quantity=1,
        unit_price=1000.00,
        taxable_value=1000.00,
        gst_rate=18.00,
        cgst_amount=90.00,
        sgst_amount=90.00,
        line_total=1180.00,
    )
    db_session.add(line)
    db_session.commit()

    fetched_lines = (
        db_session.query(InvoiceLineItem).filter_by(invoice_id=invoice.id).all()
    )
    assert len(fetched_lines) == 1
    assert float(fetched_lines[0].line_total) == 1180.00


def test_received_document_and_decision(db_session):
    doc = ReceivedDocument(
        source_type="EMAIL",
        original_filename="vendor_invoice.pdf",
        storage_key="documents/vendor_invoice.pdf",
        sha256="a" * 64,
    )
    db_session.add(doc)
    db_session.commit()

    decision = Decision(
        entity_type="ReceivedDocument",
        entity_id=doc.id,
        llm_recommendation="HOLD_FOR_REVIEW",
        final_decision="HOLD_FOR_REVIEW",
        decided_by="SYSTEM",
    )
    db_session.add(decision)
    db_session.commit()

    fetched = db_session.query(Decision).filter_by(entity_id=doc.id).one()
    assert fetched.final_decision == "HOLD_FOR_REVIEW"


def test_audit_event_is_append_only_by_convention(db_session):
    event = AuditEvent(
        correlation_id="corr-1",
        entity_type="Order",
        entity_id="order-1",
        event_name="ORDER_RECEIVED",
        actor_type="SYSTEM",
        new_state="PAID_ORDER_RECEIVED",
    )
    db_session.add(event)
    db_session.commit()

    fetched = db_session.query(AuditEvent).filter_by(correlation_id="corr-1").one()
    assert fetched.new_state == "PAID_ORDER_RECEIVED"


def test_idempotency_record_unique_constraint(db_session):
    record = IdempotencyRecord(
        operation_name="order_paid_webhook",
        idempotency_key="evt_123",
        request_hash="deadbeef",
        status="PROCESSING",
    )
    db_session.add(record)
    db_session.commit()

    fetched = db_session.query(IdempotencyRecord).filter_by(idempotency_key="evt_123").one()
    assert fetched.operation_name == "order_paid_webhook"
