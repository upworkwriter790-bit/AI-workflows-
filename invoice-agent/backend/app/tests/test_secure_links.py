"""Spec §16 cases 14-16."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.invoice_delivery import InvoiceDelivery
from app.models.invoice_document import InvoiceDocument
from app.services.secure_links.service import LinkAccessDenied, create_link, resolve_and_consume, revoke_link


def _seed_document_and_delivery(db):
    doc = InvoiceDocument(
        original_filename="inv.pdf", sanitized_filename="inv.pdf", mime_type="application/pdf",
        byte_size=len(b"%PDF-1.4"), sha256="f" * 64, storage_key="invoice-documents/x/inv.pdf", source="API",
    )
    db.add(doc)
    db.commit()
    delivery = InvoiceDelivery(
        document_id=doc.id, recipient_name="Buyer", recipient_email="buyer@example.com",
        requested_channels_json=["email"], idempotency_key="link-test", correlation_id="corr-link",
    )
    db.add(delivery)
    db.commit()
    return doc, delivery


def test_secure_link_expires_after_configured_time(db_session):
    doc, delivery = _seed_document_and_delivery(db_session)
    created = create_link(db_session, document_id=doc.id, delivery_id=delivery.id, expiry_days=7, max_downloads=3)

    # Simulate the link having already expired.
    created.record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(created.record)
    db_session.commit()

    try:
        resolve_and_consume(db_session, created.token)
        raised = False
    except LinkAccessDenied as exc:
        raised = True
        assert exc.reason == "expired"
    assert raised


def test_revoked_secure_link_cannot_be_accessed(db_session):
    doc, delivery = _seed_document_and_delivery(db_session)
    created = create_link(db_session, document_id=doc.id, delivery_id=delivery.id, expiry_days=7, max_downloads=3)
    revoke_link(db_session, created.record)

    try:
        resolve_and_consume(db_session, created.token)
        raised = False
    except LinkAccessDenied as exc:
        raised = True
        assert exc.reason == "revoked"
    assert raised


def test_secure_link_respects_max_download_count(db_session):
    doc, delivery = _seed_document_and_delivery(db_session)
    created = create_link(db_session, document_id=doc.id, delivery_id=delivery.id, expiry_days=7, max_downloads=2)

    resolve_and_consume(db_session, created.token)
    resolve_and_consume(db_session, created.token)

    try:
        resolve_and_consume(db_session, created.token)
        raised = False
    except LinkAccessDenied as exc:
        raised = True
        assert exc.reason == "download_limit_reached"
    assert raised


def test_download_route_streams_valid_pdf(harness):
    doc = InvoiceDocument(
        original_filename="inv.pdf", sanitized_filename="inv.pdf", mime_type="application/pdf",
        byte_size=14, sha256="g" * 64, storage_key="invoice-documents/y/inv.pdf", source="API",
    )
    db = harness.SessionLocal()
    try:
        from app.services.storage.factory import get_storage_adapter

        storage = get_storage_adapter(harness.settings)
        storage.save(doc.storage_key, b"%PDF-1.4\n%%EOF", content_type="application/pdf")

        db.add(doc)
        db.commit()
        delivery = InvoiceDelivery(
            document_id=doc.id, recipient_name="Buyer", recipient_email="buyer@example.com",
            requested_channels_json=["email"], idempotency_key="link-route", correlation_id="corr-route",
        )
        db.add(delivery)
        db.commit()
        link = create_link(db, document_id=doc.id, delivery_id=delivery.id, expiry_days=7, max_downloads=3)
        token = link.token
    finally:
        db.close()

    resp = harness.client.get(f"/d/{token}")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF-")


def test_download_route_rejects_unknown_token(harness):
    resp = harness.client.get("/d/not-a-real-token")
    assert resp.status_code == 404
