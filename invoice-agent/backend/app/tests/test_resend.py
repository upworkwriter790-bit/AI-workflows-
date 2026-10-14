"""Spec §16 cases 17-18."""

from __future__ import annotations

from app.models.delivery_attempt import DeliveryAttempt
from app.models.invoice_document import InvoiceDocument

PDF_BYTES = b"%PDF-1.4\n%%EOF"


def _upload(client, headers, **overrides):
    data = {
        "recipient_name": "Buyer Pvt Ltd",
        "recipient_email": "buyer@example.com",
        "requested_channels": ["email"],
        "idempotency_key": "idem-resend-1",
    }
    data.update(overrides)
    files = {"invoice_file": ("invoice.pdf", PDF_BYTES, "application/pdf")}
    return client.post("/api/v1/invoice-deliveries", data=data, files=files, headers=headers)


def test_resend_requires_manager_or_admin_role(harness):
    resp = _upload(harness.client, harness.admin_headers, idempotency_key="idem-r1")
    delivery_id = resp.json()["delivery_id"]

    denied = harness.client.post(
        f"/api/v1/invoice-deliveries/{delivery_id}/resend",
        data={"channels": ["email"], "reason": "customer asked again"},
        headers=harness.viewer_headers,
    )
    assert denied.status_code == 403


def test_resend_requires_a_reason(harness):
    resp = _upload(harness.client, harness.admin_headers, idempotency_key="idem-r2")
    delivery_id = resp.json()["delivery_id"]

    missing_reason = harness.client.post(
        f"/api/v1/invoice-deliveries/{delivery_id}/resend",
        data={"channels": ["email"], "reason": ""},
        headers=harness.manager_headers,
    )
    assert missing_reason.status_code == 422


def test_resend_creates_new_attempt_not_new_document(harness):
    resp = _upload(harness.client, harness.admin_headers, idempotency_key="idem-r3")
    delivery_id = resp.json()["delivery_id"]

    ok = harness.client.post(
        f"/api/v1/invoice-deliveries/{delivery_id}/resend",
        data={"channels": ["email"], "reason": "customer says it bounced, resending"},
        headers=harness.manager_headers,
    )
    assert ok.status_code == 200

    db = harness.SessionLocal()
    try:
        attempts = (
            db.query(DeliveryAttempt)
            .filter_by(delivery_id=delivery_id, channel="EMAIL")
            .order_by(DeliveryAttempt.attempt_number)
            .all()
        )
        assert len(attempts) == 2
        assert attempts[0].is_resend is False
        assert attempts[1].is_resend is True
        assert attempts[1].resend_reason == "customer says it bounced, resending"
        assert db.query(InvoiceDocument).count() == 1
    finally:
        db.close()


def test_resend_audit_event_records_user_identity_and_reason(harness):
    resp = _upload(harness.client, harness.admin_headers, idempotency_key="idem-r4")
    delivery_id = resp.json()["delivery_id"]

    harness.client.post(
        f"/api/v1/invoice-deliveries/{delivery_id}/resend",
        data={"channels": ["email"], "reason": "manual retry requested by finance"},
        headers=harness.manager_headers,
    )

    detail = harness.client.get(f"/api/v1/invoice-deliveries/{delivery_id}", headers=harness.admin_headers)
    timeline = detail.json()["audit_timeline"]
    resend_events = [e for e in timeline if e["event_name"] == "MANUAL_RESEND_REQUESTED"]
    assert len(resend_events) == 1
    assert resend_events[0]["actor_type"] == "USER"
    assert resend_events[0]["safe_payload"]["reason"] == "manual retry requested by finance"
