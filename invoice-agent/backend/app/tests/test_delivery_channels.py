"""Spec §16 cases 7-13."""

from __future__ import annotations

from app.models.delivery_attempt import DeliveryAttempt
from app.models.invoice_delivery import InvoiceDelivery

PDF_BYTES = b"%PDF-1.4\n%%EOF"


def _upload(client, headers, **overrides):
    data = {
        "recipient_name": "Buyer Pvt Ltd",
        "recipient_email": "buyer@example.com",
        "recipient_phone": "+919876543210",
        "requested_channels": ["email", "whatsapp"],
        "idempotency_key": "idem-channels-1",
    }
    data.update(overrides)
    files = {"invoice_file": ("invoice.pdf", PDF_BYTES, "application/pdf")}
    return client.post("/api/v1/invoice-deliveries", data=data, files=files, headers=headers)


def _upload_and_approve(client, headers, **overrides):
    """require_human_approval defaults to false — the upload itself
    dispatches immediately, so there's no separate approve call needed
    (kept the name since every test below calls it expecting dispatch
    outcomes to already be visible on the response).
    """
    resp = _upload(client, headers, **overrides)
    assert resp.status_code == 201
    return resp


def test_email_delivery_creates_attempt_with_pdf_attachment(harness):
    resp = _upload_and_approve(
        harness.client, harness.admin_headers, idempotency_key="idem-c1", requested_channels=["email"]
    )
    delivery_id = resp.json()["delivery_id"]

    db = harness.SessionLocal()
    try:
        attempts = db.query(DeliveryAttempt).filter_by(delivery_id=delivery_id, channel="EMAIL").all()
        assert len(attempts) == 1
        assert attempts[0].status == "SENT"
        assert attempts[0].provider_message_id is not None
    finally:
        db.close()


def test_whatsapp_delivery_creates_notification_attempt(harness):
    resp = _upload_and_approve(
        harness.client, harness.admin_headers, idempotency_key="idem-c2", requested_channels=["whatsapp"]
    )
    delivery_id = resp.json()["delivery_id"]

    db = harness.SessionLocal()
    try:
        attempts = db.query(DeliveryAttempt).filter_by(delivery_id=delivery_id, channel="WHATSAPP").all()
        assert len(attempts) == 1
        assert attempts[0].status == "SENT"
        assert attempts[0].provider_message_id is not None
    finally:
        db.close()


def test_email_provider_delivered_webhook_updates_status(harness):
    resp = _upload_and_approve(
        harness.client, harness.admin_headers, idempotency_key="idem-c3", requested_channels=["email"]
    )
    delivery_id = resp.json()["delivery_id"]

    db = harness.SessionLocal()
    try:
        attempt = db.query(DeliveryAttempt).filter_by(delivery_id=delivery_id, channel="EMAIL").one()
        message_id = attempt.provider_message_id
    finally:
        db.close()

    callback = harness.client.post(
        "/api/v1/webhooks/email", json={"message_id": message_id, "event_type": "delivered"}
    )
    assert callback.status_code == 200
    assert callback.json()["status"] == "processed"

    db = harness.SessionLocal()
    try:
        attempt = db.query(DeliveryAttempt).filter_by(id=attempt.id).one()
        assert attempt.status == "DELIVERED"
        delivery = db.query(InvoiceDelivery).filter_by(id=delivery_id).one()
        assert delivery.status == "COMPLETED"
    finally:
        db.close()


def test_whatsapp_provider_delivered_then_read_callback_updates_status(harness):
    resp = _upload_and_approve(
        harness.client, harness.admin_headers, idempotency_key="idem-c4", requested_channels=["whatsapp"]
    )
    delivery_id = resp.json()["delivery_id"]

    db = harness.SessionLocal()
    try:
        attempt = db.query(DeliveryAttempt).filter_by(delivery_id=delivery_id, channel="WHATSAPP").one()
        message_id = attempt.provider_message_id
    finally:
        db.close()

    delivered = harness.client.post(
        "/api/v1/webhooks/whatsapp", json={"message_id": message_id, "status": "delivered"}
    )
    assert delivered.status_code == 200

    read = harness.client.post("/api/v1/webhooks/whatsapp", json={"message_id": message_id, "status": "read"})
    assert read.status_code == 200

    db = harness.SessionLocal()
    try:
        attempt = db.query(DeliveryAttempt).filter_by(id=attempt.id).one()
        assert attempt.status == "READ"
    finally:
        db.close()


def test_transient_email_failure_schedules_retry_then_eventually_fails(harness, monkeypatch):
    from app.services.email.mock import MockEmailProvider
    from app.workflows import delivery_workflow

    failing_provider = MockEmailProvider()
    failing_provider.fail_mode = "transient"
    monkeypatch.setattr(delivery_workflow, "get_email_provider", lambda settings: failing_provider)

    resp = _upload_and_approve(
        harness.client, harness.admin_headers, idempotency_key="idem-c5", requested_channels=["email"]
    )
    delivery_id = resp.json()["delivery_id"]

    db = harness.SessionLocal()
    try:
        attempt = db.query(DeliveryAttempt).filter_by(delivery_id=delivery_id, channel="EMAIL").one()
        # Retries are exhausted synchronously by the test harness's fake
        # `.delay()` (see conftest.py) rather than waiting on real timers.
        assert attempt.status == "FAILED"
        assert attempt.attempt_number == harness.settings.retry_max_attempts
        assert attempt.error_code is not None
    finally:
        db.close()


def test_permanent_email_failure_does_not_retry(harness, monkeypatch):
    from app.services.email.mock import MockEmailProvider
    from app.workflows import delivery_workflow

    failing_provider = MockEmailProvider()
    failing_provider.fail_mode = "permanent"
    monkeypatch.setattr(delivery_workflow, "get_email_provider", lambda settings: failing_provider)

    resp = _upload_and_approve(
        harness.client, harness.admin_headers, idempotency_key="idem-c6", requested_channels=["email"]
    )
    delivery_id = resp.json()["delivery_id"]

    db = harness.SessionLocal()
    try:
        attempt = db.query(DeliveryAttempt).filter_by(delivery_id=delivery_id, channel="EMAIL").one()
        assert attempt.status == "FAILED"
        assert attempt.attempt_number == 1  # never incremented — no retry attempted
    finally:
        db.close()


def test_whatsapp_failure_does_not_prevent_successful_email(harness, monkeypatch):
    from app.services.whatsapp.mock import MockWhatsAppProvider
    from app.workflows import delivery_workflow

    failing_whatsapp = MockWhatsAppProvider()
    failing_whatsapp.fail_mode = "permanent"
    monkeypatch.setattr(delivery_workflow, "get_whatsapp_provider", lambda settings: failing_whatsapp)

    resp = _upload_and_approve(harness.client, harness.admin_headers, idempotency_key="idem-c7")
    delivery_id = resp.json()["delivery_id"]

    db = harness.SessionLocal()
    try:
        email_attempt = db.query(DeliveryAttempt).filter_by(delivery_id=delivery_id, channel="EMAIL").one()
        whatsapp_attempt = db.query(DeliveryAttempt).filter_by(delivery_id=delivery_id, channel="WHATSAPP").one()
        assert email_attempt.status == "SENT"
        assert whatsapp_attempt.status == "FAILED"

        delivery = db.query(InvoiceDelivery).filter_by(id=delivery_id).one()
        assert delivery.status == "PARTIALLY_DELIVERED"
    finally:
        db.close()


def test_partial_delivery_is_correctly_shown_in_detail_view(harness, monkeypatch):
    from app.services.whatsapp.mock import MockWhatsAppProvider
    from app.workflows import delivery_workflow

    failing_whatsapp = MockWhatsAppProvider()
    failing_whatsapp.fail_mode = "permanent"
    monkeypatch.setattr(delivery_workflow, "get_whatsapp_provider", lambda settings: failing_whatsapp)

    resp = _upload_and_approve(harness.client, harness.admin_headers, idempotency_key="idem-c8")
    delivery_id = resp.json()["delivery_id"]

    detail = harness.client.get(f"/api/v1/invoice-deliveries/{delivery_id}", headers=harness.viewer_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "PARTIALLY_DELIVERED"
    statuses = {a["channel"]: a["status"] for a in body["attempts"]}
    assert statuses["EMAIL"] == "SENT"
    assert statuses["WHATSAPP"] == "FAILED"
