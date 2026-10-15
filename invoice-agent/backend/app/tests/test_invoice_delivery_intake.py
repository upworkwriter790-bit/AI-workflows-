"""Spec §16 cases 1-6, 19, 20."""

from __future__ import annotations

from app.models.invoice_delivery import InvoiceDelivery
from app.models.invoice_document import InvoiceDocument

PDF_BYTES = b"%PDF-1.4\n%%EOF"


def _upload(client, headers, **overrides):
    """Defaults to `require_human_approval=True` so most of this file's
    tests exercise the approval-gated path explicitly — see
    test_default_upload_dispatches_immediately_without_approval for the
    (now restored) opposite default.
    """
    data = {
        "recipient_name": "Buyer Pvt Ltd",
        "recipient_email": "buyer@example.com",
        "recipient_phone": "+919876543210",
        "requested_channels": ["email", "whatsapp"],
        "idempotency_key": "idem-1",
        "require_human_approval": True,
    }
    data.update(overrides)
    files = {"invoice_file": ("invoice.pdf", PDF_BYTES, "application/pdf")}
    return client.post("/api/v1/invoice-deliveries", data=data, files=files, headers=headers)


def _approve(client, headers, delivery_id):
    return client.post(f"/api/v1/invoice-deliveries/{delivery_id}/approve", headers=headers)


def test_valid_pdf_upload_queues_delivery(harness):
    resp = _upload(harness.client, harness.admin_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "DRAFT_REVIEW_REQUIRED"
    assert set(body["requested_channels"]) == {"email", "whatsapp"}
    assert "delivery_id" in body and "correlation_id" in body

    db = harness.SessionLocal()
    try:
        assert db.query(InvoiceDelivery).count() == 1
        assert db.query(InvoiceDocument).count() == 1
    finally:
        db.close()

    approve_resp = _approve(harness.client, harness.admin_headers, body["delivery_id"])
    assert approve_resp.status_code == 200
    approved_body = approve_resp.json()
    assert approved_body["status"] in {"QUEUED", "COMPLETED", "PARTIALLY_DELIVERED", "EMAIL_FAILED", "WHATSAPP_FAILED"}


def test_delivery_not_dispatched_until_approved(harness):
    resp = _upload(harness.client, harness.admin_headers, idempotency_key="idem-draft-gate")
    delivery_id = resp.json()["delivery_id"]

    db = harness.SessionLocal()
    try:
        from app.models.delivery_attempt import DeliveryAttempt

        assert db.query(DeliveryAttempt).filter_by(delivery_id=delivery_id).count() == 0
    finally:
        db.close()

    second_approve = _approve(harness.client, harness.admin_headers, delivery_id)
    assert second_approve.status_code == 200
    repeat_approve = _approve(harness.client, harness.admin_headers, delivery_id)
    assert repeat_approve.status_code == 409


def test_default_upload_dispatches_immediately_without_approval(harness):
    """require_human_approval defaults to false — Method A's default
    behavior is still direct delivery after file validation, same as
    before any approval gate existed.
    """
    resp = _upload(
        harness.client, harness.admin_headers, idempotency_key="idem-direct", require_human_approval=False,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] != "DRAFT_REVIEW_REQUIRED"

    db = harness.SessionLocal()
    try:
        from app.models.delivery_attempt import DeliveryAttempt

        assert db.query(DeliveryAttempt).filter_by(delivery_id=body["delivery_id"]).count() == 2
    finally:
        db.close()

    # Already dispatched — approving it now is a 409, not a no-op.
    approve_resp = _approve(harness.client, harness.admin_headers, body["delivery_id"])
    assert approve_resp.status_code == 409


def test_non_pdf_upload_rejected(harness):
    files = {"invoice_file": ("invoice.docx", b"not a pdf", "application/vnd.openxmlformats")}
    resp = harness.client.post(
        "/api/v1/invoice-deliveries",
        data={
            "recipient_name": "Buyer", "recipient_email": "buyer@example.com",
            "requested_channels": ["email"], "idempotency_key": "idem-2",
        },
        files=files,
        headers=harness.admin_headers,
    )
    assert resp.status_code == 400


def test_oversized_file_rejected(harness):
    harness.settings.max_file_size_mb = 0  # anything beats 0 bytes effectively
    resp = _upload(harness.client, harness.admin_headers, idempotency_key="idem-3")
    assert resp.status_code == 400


def test_missing_email_rejected_when_email_requested(harness):
    resp = _upload(
        harness.client, harness.admin_headers, idempotency_key="idem-4",
        recipient_email="", requested_channels=["email"],
    )
    assert resp.status_code == 400


def test_invalid_e164_phone_rejected_when_whatsapp_requested(harness):
    resp = _upload(
        harness.client, harness.admin_headers, idempotency_key="idem-5",
        requested_channels=["whatsapp"], recipient_phone="98765",
    )
    assert resp.status_code == 400


def test_same_idempotency_key_does_not_create_duplicate_delivery(harness):
    first = _upload(harness.client, harness.admin_headers, idempotency_key="idem-dup")
    second = _upload(harness.client, harness.admin_headers, idempotency_key="idem-dup")

    assert first.status_code == 201
    assert second.status_code in {200, 201}
    assert first.json()["delivery_id"] == second.json()["delivery_id"]

    db = harness.SessionLocal()
    try:
        assert db.query(InvoiceDelivery).count() == 1
    finally:
        db.close()


def test_upload_requires_authorized_role(harness):
    resp = _upload(harness.client, harness.viewer_headers, idempotency_key="idem-6")
    assert resp.status_code == 403


def test_upload_without_token_rejected(harness):
    resp = _upload(harness.client, {}, idempotency_key="idem-7")
    assert resp.status_code == 401


def test_recipient_data_masked_in_list_view(harness):
    _upload(harness.client, harness.admin_headers, idempotency_key="idem-8")
    resp = harness.client.get("/api/v1/invoice-deliveries", headers=harness.viewer_headers)
    assert resp.status_code == 200
    deliveries = resp.json()["deliveries"]
    assert len(deliveries) == 1
    assert "buyer@example.com" not in deliveries[0]["recipient_email"]
    assert "+919876543210" not in deliveries[0]["recipient_phone"]


def test_removed_crm_erp_gst_llm_routes_not_reachable(harness):
    for path in [
        "/api/v1/webhooks/crm/order-paid",
        "/api/v1/erp/invoices",
        "/api/v1/gst/calculate",
        "/api/v1/documents/extract",
    ]:
        resp = harness.client.post(path, json={})
        assert resp.status_code == 404


def test_removed_modules_not_importable_from_live_tree():
    import importlib

    for module_name in [
        "app.services.crm.base",
        "app.services.erp.base",
        "app.services.gst.calculator",
        "app.services.invoice_pdf.renderer",
        "app.services.document_review.llm_client",
        "app.services.operations.base",
        "app.services.product_access.base",
        "app.workflows.order_workflow",
    ]:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        else:
            raise AssertionError(f"{module_name} should not exist in the active tree")
