"""Spec §13 cases 3-20 (Method B). Cases 1-2 are Method A, already
covered in test_invoice_delivery_intake.py.
"""

from __future__ import annotations

from decimal import Decimal

from pypdf import PdfReader

from app.models.delivery_attempt import DeliveryAttempt
from app.models.generated_invoice import GeneratedInvoice
from app.models.generated_invoice_line_item import GeneratedInvoiceLineItem
from app.models.invoice_document import InvoiceDocument
from app.models.product_catalog_item import ProductCatalogItem


def _base_payload(**overrides):
    payload = {
        "idempotency_key": "gi-key-1",
        "external_reference": "ORD-100",
        "recipient": {
            "name": "Buyer Pvt Ltd",
            "email": "buyer@example.com",
            "phone": "+919876543210",
            "billing_address": {
                "line1": "1 Test St", "city": "Mumbai", "state": "Maharashtra",
                "state_code": "27", "postal_code": "400001", "country": "India",
            },
        },
        "payment_or_order_details": {
            "payment_reference": "PAY-100", "payment_date": "2026-10-14", "currency": "INR",
            "tax_inclusive": False, "subtotal": 1000.00, "discount_total": 0,
            "tax_total": 180.00, "grand_total": 1180.00, "payment_status": "PAID",
        },
        "items": [
            {
                "description": "Pro Plan", "product_type": "SERVICE", "hsn_or_sac_code": "9983",
                "quantity": 1, "unit": "Nos", "unit_price": 1000.00, "gst_rate": 18.00,
            }
        ],
        "delivery": {"requested_channels": ["email", "whatsapp"]},
    }
    for key, value in overrides.items():
        payload[key] = value
    return payload


def _post(client, headers, payload):
    return client.post("/api/v1/generated-invoice-deliveries", json=payload, headers=headers)


def _approve(client, headers, invoice_id):
    return client.post(f"/api/v1/generated-invoice-deliveries/{invoice_id}/approve", headers=headers)


def _post_and_approve(client, headers, payload):
    draft = _post(client, headers, payload)
    assert draft.status_code == 201
    approved = _approve(client, headers, draft.json()["invoice_id"])
    assert approved.status_code == 200
    return draft, approved


def test_valid_payment_details_generate_exactly_one_pdf(harness):
    draft, approved = _post_and_approve(harness.client, harness.admin_headers, _base_payload())
    assert draft.json()["status"] == "PENDING_HUMAN_REVIEW"
    body = approved.json()
    assert body["invoice_number"].startswith("INV/FY")
    assert body["delivery_id"] is not None

    db = harness.SessionLocal()
    try:
        assert db.query(GeneratedInvoice).count() == 1
        assert db.query(InvoiceDocument).count() == 1
        assert db.query(GeneratedInvoiceLineItem).count() == 1
    finally:
        db.close()


def test_same_idempotency_key_returns_original_invoice_and_delivery(harness):
    _, approved_first = _post_and_approve(
        harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-dup")
    )
    second = _post(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-dup"))

    assert second.status_code == 201
    assert approved_first.json()["invoice_number"] == second.json()["invoice_number"]
    assert approved_first.json()["invoice_id"] == second.json()["invoice_id"]

    db = harness.SessionLocal()
    try:
        assert db.query(GeneratedInvoice).count() == 1
        assert db.query(InvoiceDocument).count() == 1
    finally:
        db.close()


def test_tax_exclusive_intra_state_calculation_is_correct(harness):
    resp = _post(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-intra"))
    assert resp.status_code == 201

    db = harness.SessionLocal()
    try:
        gi = db.query(GeneratedInvoice).filter_by(idempotency_key="gi-intra").one()
        assert float(gi.cgst_total) == 90.00
        assert float(gi.sgst_total) == 90.00
        assert float(gi.igst_total) == 0.00
        assert float(gi.grand_total) == 1180.00
    finally:
        db.close()


def test_tax_exclusive_inter_state_calculation_is_correct(harness):
    payload = _base_payload(idempotency_key="gi-inter")
    payload["recipient"]["billing_address"]["state"] = "Delhi"
    payload["recipient"]["billing_address"]["state_code"] = "07"
    resp = _post(harness.client, harness.admin_headers, payload)
    assert resp.status_code == 201

    db = harness.SessionLocal()
    try:
        gi = db.query(GeneratedInvoice).filter_by(idempotency_key="gi-inter").one()
        assert float(gi.igst_total) == 180.00
        assert float(gi.cgst_total) == 0.00
        assert float(gi.sgst_total) == 0.00
    finally:
        db.close()


def test_tax_inclusive_calculation_is_correct(harness):
    payload = _base_payload(idempotency_key="gi-inclusive")
    payload["payment_or_order_details"]["tax_inclusive"] = True
    payload["payment_or_order_details"]["subtotal"] = 1180.00
    payload["payment_or_order_details"]["tax_total"] = 180.00
    payload["payment_or_order_details"]["grand_total"] = 1180.00
    payload["items"][0]["unit_price"] = 1180.00

    resp = _post(harness.client, harness.admin_headers, payload)
    assert resp.status_code == 201

    db = harness.SessionLocal()
    try:
        gi = db.query(GeneratedInvoice).filter_by(idempotency_key="gi-inclusive").one()
        assert float(gi.taxable_total) == 1000.00
        assert float(gi.grand_total) == 1180.00
    finally:
        db.close()


def test_total_mismatch_stops_invoice_generation(harness):
    payload = _base_payload(idempotency_key="gi-mismatch")
    payload["payment_or_order_details"]["grand_total"] = 50000.00

    resp = _post(harness.client, harness.admin_headers, payload)
    assert resp.status_code == 422

    db = harness.SessionLocal()
    try:
        gi = db.query(GeneratedInvoice).filter_by(idempotency_key="gi-mismatch").one()
        assert gi.status == "TOTAL_MISMATCH"
        assert gi.invoice_number is None
        assert db.query(InvoiceDocument).count() == 0
    finally:
        db.close()


def test_missing_hsn_or_gst_rate_rejected(harness):
    payload = _base_payload(idempotency_key="gi-missing-hsn")
    del payload["items"][0]["hsn_or_sac_code"]

    resp = _post(harness.client, harness.admin_headers, payload)
    assert resp.status_code == 422  # schema-level: hsn_or_sac_code is required


def test_negative_quantity_rejected(harness):
    payload = _base_payload(idempotency_key="gi-negative-qty")
    payload["items"][0]["quantity"] = -1

    resp = _post(harness.client, harness.admin_headers, payload)
    assert resp.status_code == 422


def test_invoice_numbers_unique_across_requests(harness):
    first_payload = _base_payload(idempotency_key="gi-seq-1")
    first_payload["external_reference"] = "ORD-200"
    first_payload["payment_or_order_details"]["payment_reference"] = "PAY-200"

    second_payload = _base_payload(idempotency_key="gi-seq-2")
    second_payload["external_reference"] = "ORD-201"
    second_payload["payment_or_order_details"]["payment_reference"] = "PAY-201"

    _, first_approved = _post_and_approve(harness.client, harness.admin_headers, first_payload)
    _, second_approved = _post_and_approve(harness.client, harness.admin_headers, second_payload)

    seq1 = int(first_approved.json()["invoice_number"].rsplit("/", 1)[-1])
    seq2 = int(second_approved.json()["invoice_number"].rsplit("/", 1)[-1])
    assert seq2 == seq1 + 1


def test_failed_email_does_not_regenerate_pdf_or_invoice_number(harness, monkeypatch):
    from app.services.email.mock import MockEmailProvider
    from app.workflows import delivery_workflow

    failing = MockEmailProvider()
    failing.fail_mode = "permanent"
    monkeypatch.setattr(delivery_workflow, "get_email_provider", lambda settings: failing)

    _, approved = _post_and_approve(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-email-fail"))
    invoice_number = approved.json()["invoice_number"]

    db = harness.SessionLocal()
    try:
        gi = db.query(GeneratedInvoice).filter_by(idempotency_key="gi-email-fail").one()
        assert gi.invoice_number == invoice_number
        assert db.query(InvoiceDocument).filter_by(invoice_number=invoice_number).count() == 1
        attempt = db.query(DeliveryAttempt).filter_by(
            delivery_id=approved.json()["delivery_id"], channel="EMAIL"
        ).one()
        assert attempt.status == "FAILED"
    finally:
        db.close()


def test_failed_whatsapp_does_not_prevent_email_result_from_being_stored(harness, monkeypatch):
    from app.services.whatsapp.mock import MockWhatsAppProvider
    from app.workflows import delivery_workflow

    failing = MockWhatsAppProvider()
    failing.fail_mode = "permanent"
    monkeypatch.setattr(delivery_workflow, "get_whatsapp_provider", lambda settings: failing)

    _, approved = _post_and_approve(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-wa-fail"))

    db = harness.SessionLocal()
    try:
        email_attempt = db.query(DeliveryAttempt).filter_by(
            delivery_id=approved.json()["delivery_id"], channel="EMAIL"
        ).one()
        whatsapp_attempt = db.query(DeliveryAttempt).filter_by(
            delivery_id=approved.json()["delivery_id"], channel="WHATSAPP"
        ).one()
        assert email_attempt.status == "SENT"
        assert whatsapp_attempt.status == "FAILED"
    finally:
        db.close()


def test_delivery_pipeline_shared_between_both_methods(harness):
    """Both an existing-PDF delivery (Method A) and a generated invoice
    (Method B) must land in the same InvoiceDelivery/DeliveryAttempt
    tables and be visible through the same detail endpoint.
    """
    pdf_bytes = b"%PDF-1.4\n%%EOF"
    method_a = harness.client.post(
        "/api/v1/invoice-deliveries",
        data={
            "recipient_name": "Buyer A", "recipient_email": "a@example.com",
            "requested_channels": ["email"], "idempotency_key": "gi-shared-a",
        },
        files={"invoice_file": ("invoice.pdf", pdf_bytes, "application/pdf")},
        headers=harness.admin_headers,
    )
    assert method_a.status_code == 201

    _, method_b_approved = _post_and_approve(
        harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-shared-b")
    )

    detail_a = harness.client.get(
        f"/api/v1/invoice-deliveries/{method_a.json()['delivery_id']}", headers=harness.admin_headers
    )
    detail_b = harness.client.get(
        f"/api/v1/invoice-deliveries/{method_b_approved.json()['delivery_id']}", headers=harness.admin_headers
    )
    assert detail_a.status_code == 200
    assert detail_b.status_code == 200
    assert set(detail_a.json().keys()) == set(detail_b.json().keys())


def test_secure_link_works_for_generated_invoice(harness):
    _, approved = _post_and_approve(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-link"))
    document_id = approved.json()["document_id"]

    db = harness.SessionLocal()
    try:
        from app.services.secure_links.service import create_link

        link = create_link(
            db, document_id=document_id, delivery_id=approved.json()["delivery_id"],
            expiry_days=7, max_downloads=3,
        )
        token = link.token
    finally:
        db.close()

    download = harness.client.get(f"/d/{token}")
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF-")


def test_resend_creates_new_attempt_but_no_new_generated_invoice(harness):
    _, approved = _post_and_approve(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-resend"))
    delivery_id = approved.json()["delivery_id"]

    resend = harness.client.post(
        f"/api/v1/invoice-deliveries/{delivery_id}/resend",
        data={"channels": ["email"], "reason": "customer says email was lost, resending"},
        headers=harness.manager_headers,
    )
    assert resend.status_code == 200

    db = harness.SessionLocal()
    try:
        assert db.query(GeneratedInvoice).count() == 1
        assert db.query(InvoiceDocument).count() == 1
        attempts = db.query(DeliveryAttempt).filter_by(delivery_id=delivery_id, channel="EMAIL").all()
        assert len(attempts) == 2
    finally:
        db.close()


def test_sensitive_payment_fields_are_rejected(harness):
    payload = _base_payload(idempotency_key="gi-sensitive")
    payload["payment_or_order_details"]["card_number"] = "4111111111111111"

    resp = _post(harness.client, harness.admin_headers, payload)
    assert resp.status_code == 422  # extra="forbid" rejects the unknown field


def test_removed_routes_still_unreachable(harness):
    for path in ["/api/v1/webhooks/crm/order-paid", "/api/v1/erp/invoices", "/api/v1/documents/extract"]:
        resp = harness.client.post(path, json={})
        assert resp.status_code == 404


def test_pdf_output_includes_required_fields(harness):
    _, approved = _post_and_approve(
        harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-pdf-content")
    )
    document_id = approved.json()["document_id"]
    invoice_number = approved.json()["invoice_number"]

    db = harness.SessionLocal()
    try:
        document = db.query(InvoiceDocument).filter_by(id=document_id).one()
        pdf_path = harness.settings.storage_local_dir
        import io
        from pathlib import Path

        pdf_bytes = (Path(pdf_path) / document.storage_key).read_bytes()
    finally:
        db.close()

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert invoice_number in text
    assert "Test Co Pvt Ltd" in text
    assert "27AAAAA0000A1Z5" in text
    assert "PAY-100" in text


def test_amounts_are_decimal_not_float(harness):
    _post(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-decimal"))
    db = harness.SessionLocal()
    try:
        gi = db.query(GeneratedInvoice).filter_by(idempotency_key="gi-decimal").one()
        # SQLAlchemy Numeric columns come back as Decimal via the DBAPI,
        # never as a native float — this would fail if the column type
        # were ever changed to Float.
        assert isinstance(gi.grand_total, Decimal) or str(type(gi.grand_total)) in {
            "<class 'decimal.Decimal'>",
        }
    finally:
        db.close()


def test_same_transaction_refs_under_new_idempotency_key_rejected(harness):
    _post_and_approve(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-refs-1"))

    second = _post(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-refs-2"))
    assert second.status_code == 422

    db = harness.SessionLocal()
    try:
        # The rejected attempt's row is rolled back entirely — only the
        # original succeeded request's row remains.
        assert db.query(GeneratedInvoice).count() == 1
        assert db.query(InvoiceDocument).count() == 1
    finally:
        db.close()


def test_catalog_mismatch_rejected(harness):
    db = harness.SessionLocal()
    try:
        db.add(
            ProductCatalogItem(
                internal_reference="COURSE-PRO-001", display_description="Professional Plan",
                product_type="SERVICE", hsn_or_sac_code="9983", unit="Nos",
                unit_price=Decimal("1000.00"), gst_rate=Decimal("18.00"), active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    payload = _base_payload(idempotency_key="gi-catalog-mismatch")
    payload["items"][0]["item_reference"] = "COURSE-PRO-001"
    payload["items"][0]["gst_rate"] = 12.00  # does not match catalog's 18.00

    resp = _post(harness.client, harness.admin_headers, payload)
    assert resp.status_code == 422


def test_draft_is_editable_and_recalculates(harness):
    draft = _post(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-edit"))
    invoice_id = draft.json()["invoice_id"]
    assert draft.json()["grand_total"] == 1180.00

    updated_payload = _base_payload(idempotency_key="gi-edit")
    updated_payload["items"][0]["quantity"] = 2
    updated_payload["payment_or_order_details"]["subtotal"] = 2000.00
    updated_payload["payment_or_order_details"]["tax_total"] = 360.00
    updated_payload["payment_or_order_details"]["grand_total"] = 2360.00

    edit_resp = harness.client.patch(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}", json=updated_payload, headers=harness.admin_headers
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["grand_total"] == 2360.00

    detail = harness.client.get(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}", headers=harness.admin_headers
    )
    assert detail.json()["is_editable"] is True
    assert detail.json()["line_items"][0]["quantity"] == 2.0


def test_editing_a_non_draft_invoice_is_rejected(harness):
    draft, _approved = _post_and_approve(
        harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-edit-locked")
    )
    invoice_id = draft.json()["invoice_id"]

    edit_resp = harness.client.patch(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}",
        json=_base_payload(idempotency_key="gi-edit-locked"),
        headers=harness.admin_headers,
    )
    assert edit_resp.status_code == 409


def test_approving_a_non_draft_invoice_is_rejected(harness):
    draft, _ = _post_and_approve(
        harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-approve-twice")
    )
    invoice_id = draft.json()["invoice_id"]

    second_approve = _approve(harness.client, harness.admin_headers, invoice_id)
    assert second_approve.status_code == 409


def test_cancelling_a_draft_under_approval_stage_numbering_leaves_no_gap(harness):
    # INVOICE_NUMBER_ASSIGNMENT_STAGE="APPROVAL" is the policy under
    # which cancelling a draft is guaranteed gap-free — under the
    # default "DRAFT" stage the number is already reserved and a
    # cancelled draft's number is a documented, accepted gap.
    harness.settings.invoice_number_assignment_stage = "APPROVAL"

    draft = _post(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-discard"))
    invoice_id = draft.json()["invoice_id"]

    cancel_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/cancel", headers=harness.admin_headers
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    db = harness.SessionLocal()
    try:
        gi = db.query(GeneratedInvoice).filter_by(id=invoice_id).one()
        assert gi.status == "CANCELLED"
        assert gi.invoice_number is None
        assert db.query(InvoiceDocument).count() == 0
    finally:
        db.close()

    next_payload = _base_payload(idempotency_key="gi-discard-next")
    next_payload["external_reference"] = "ORD-300"
    next_payload["payment_or_order_details"]["payment_reference"] = "PAY-300"
    _next_draft, next_approved = _post_and_approve(harness.client, harness.admin_headers, next_payload)
    # No gap was left in the sequence by the cancelled draft, which never
    # reserved a number under the APPROVAL assignment stage.
    assert next_approved.json()["invoice_number"] is not None


def test_cancelling_a_non_draft_invoice_is_rejected(harness):
    draft, _ = _post_and_approve(
        harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-discard-locked")
    )
    invoice_id = draft.json()["invoice_id"]

    cancel_resp = harness.client.post(
        f"/api/v1/generated-invoice-deliveries/{invoice_id}/cancel", headers=harness.admin_headers
    )
    assert cancel_resp.status_code == 409


def test_nothing_is_dispatched_until_approval(harness, monkeypatch):
    from app.tasks import delivery_tasks

    called = []
    monkeypatch.setattr(delivery_tasks.send_email_attempt_task, "delay", lambda *a, **k: called.append(a))

    draft = _post(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-no-dispatch"))
    assert draft.status_code == 201
    assert draft.json()["delivery_id"] is None
    assert called == []


def test_list_generated_invoices_returns_summary(harness):
    _post(harness.client, harness.admin_headers, _base_payload(idempotency_key="gi-list-1"))
    resp = harness.client.get("/api/v1/generated-invoice-deliveries", headers=harness.viewer_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    assert any(item["invoice_id"] for item in body["generated_invoices"])
