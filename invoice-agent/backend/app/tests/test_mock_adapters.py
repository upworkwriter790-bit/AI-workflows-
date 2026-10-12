from __future__ import annotations

import pytest

from app.services.crm.mock import MockCRMAdapter
from app.services.email.mock import MockEmailAdapter
from app.services.erp.mock import MockERPAdapter
from app.services.operations.mock import MockOperationsAdapter
from app.services.product_access.mock import MockProductAccessAdapter


def test_mock_crm_round_trip():
    crm = MockCRMAdapter()
    crm.seed_order("ORD-1", {"payment_status": "paid"})
    crm.seed_customer("CUS-1", {"name": "Test"})

    assert crm.verify_order_paid("ORD-1") is True
    assert crm.get_order("ORD-1")["payment_status"] == "paid"
    assert crm.get_customer("CUS-1")["name"] == "Test"

    task_id = crm.create_operations_task("CUS-1", "ORD-1", "INV-1", ["PROD-1"])
    assert task_id.startswith("MOCK-OPS-TASK-")

    with pytest.raises(LookupError):
        crm.get_order("ORD-UNKNOWN")


def test_mock_erp_search_before_create_and_idempotent():
    erp = MockERPAdapter()
    payload = {"external_reference": "invoice-1", "grand_total": 1180.00}

    first = erp.create_invoice_draft(payload, idempotency_key="invoice-1")
    second = erp.create_invoice_draft(payload, idempotency_key="invoice-1")

    assert first["erp_invoice_id"] == second["erp_invoice_id"]
    assert erp.get_invoice_by_external_reference("invoice-1") is not None

    erp.update_invoice_status(first["erp_invoice_id"], "POSTED")
    assert erp.get_sync_result(first["erp_invoice_id"])["status"] == "POSTED"


def test_mock_email_send_and_delivery_webhook():
    email = MockEmailAdapter()
    message_id = email.send_invoice_email(
        to_email="buyer@example.com",
        subject="Your invoice INV-1",
        body_html="<p>hi</p>",
        pdf_attachment_bytes=b"%PDF-1.4",
    )
    assert email.sent_messages[message_id]["status"] == "sent"

    result = email.receive_delivery_webhook({"message_id": message_id, "status": "delivered"})
    assert result["status"] == "delivered"
    assert email.sent_messages[message_id]["status"] == "delivered"


def test_mock_operations_and_product_access():
    ops = MockOperationsAdapter()
    reference = ops.notify_product_access_required({"customer_id": "CUS-1"})
    assert reference.startswith("MOCK-OPS-")
    assert ops.notifications[0]["payload"]["customer_id"] == "CUS-1"

    access = MockProductAccessAdapter()
    result = access.enable_access("CUS-1", ["PROD-1"])
    assert result["status"] == "ACTIVATED"
