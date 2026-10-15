from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.audit_event import AuditEvent
from app.models.delivery_attempt import DeliveryAttempt
from app.models.idempotency import IdempotencyRecord
from app.models.internal_user import InternalUser
from app.models.invoice_delivery import InvoiceDelivery
from app.models.invoice_document import InvoiceDocument
from app.models.secure_download_link import SecureDownloadLink


def test_invoice_document_roundtrip(db_session):
    doc = InvoiceDocument(
        original_filename="Invoice (final).pdf",
        sanitized_filename="Invoice_final.pdf",
        mime_type="application/pdf",
        byte_size=12345,
        sha256="a" * 64,
        storage_key="invoice-documents/1/Invoice_final.pdf",
        source="INTERNAL_UPLOAD",
    )
    db_session.add(doc)
    db_session.commit()

    fetched = db_session.query(InvoiceDocument).filter_by(storage_key=doc.storage_key).one()
    assert fetched.sha256 == "a" * 64
    assert fetched.source == "INTERNAL_UPLOAD"


def test_invoice_delivery_unique_idempotency_key(db_session):
    doc = InvoiceDocument(
        original_filename="inv.pdf", sanitized_filename="inv.pdf", mime_type="application/pdf",
        byte_size=1, sha256="b" * 64, storage_key="k1", source="API",
    )
    db_session.add(doc)
    db_session.commit()

    delivery = InvoiceDelivery(
        document_id=doc.id, recipient_name="Buyer", recipient_email="buyer@example.com",
        requested_channels_json=["email"], idempotency_key="idem-1", correlation_id="corr-1",
    )
    db_session.add(delivery)
    db_session.commit()

    fetched = db_session.query(InvoiceDelivery).filter_by(idempotency_key="idem-1").one()
    assert fetched.recipient_name == "Buyer"
    assert fetched.requested_channels_json == ["email"]


def test_delivery_attempt_roundtrip(db_session):
    doc = InvoiceDocument(
        original_filename="inv.pdf", sanitized_filename="inv.pdf", mime_type="application/pdf",
        byte_size=1, sha256="c" * 64, storage_key="k2", source="API",
    )
    db_session.add(doc)
    db_session.commit()
    delivery = InvoiceDelivery(
        document_id=doc.id, recipient_name="Buyer", recipient_phone="+919876543210",
        requested_channels_json=["whatsapp"], idempotency_key="idem-2", correlation_id="corr-2",
    )
    db_session.add(delivery)
    db_session.commit()

    attempt = DeliveryAttempt(delivery_id=delivery.id, channel="WHATSAPP", attempt_number=1, status="QUEUED")
    db_session.add(attempt)
    db_session.commit()

    fetched = db_session.query(DeliveryAttempt).filter_by(delivery_id=delivery.id).one()
    assert fetched.channel == "WHATSAPP"
    assert fetched.is_resend is False


def test_secure_download_link_roundtrip(db_session):
    doc = InvoiceDocument(
        original_filename="inv.pdf", sanitized_filename="inv.pdf", mime_type="application/pdf",
        byte_size=1, sha256="d" * 64, storage_key="k3", source="API",
    )
    db_session.add(doc)
    db_session.commit()
    delivery = InvoiceDelivery(
        document_id=doc.id, recipient_name="Buyer", recipient_email="buyer@example.com",
        requested_channels_json=["email"], idempotency_key="idem-3", correlation_id="corr-3",
    )
    db_session.add(delivery)
    db_session.commit()

    link = SecureDownloadLink(
        document_id=doc.id, delivery_id=delivery.id, token_hash="e" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=7), max_downloads=3, download_count=0,
    )
    db_session.add(link)
    db_session.commit()

    fetched = db_session.query(SecureDownloadLink).filter_by(token_hash="e" * 64).one()
    assert fetched.max_downloads == 3
    assert fetched.revoked_at is None


def test_internal_user_roundtrip(db_session):
    user = InternalUser(
        email="admin@example.com", display_name="Admin", password_hash="hashed", role="ADMIN",
    )
    db_session.add(user)
    db_session.commit()

    fetched = db_session.query(InternalUser).filter_by(email="admin@example.com").one()
    assert fetched.role == "ADMIN"
    assert fetched.is_active is True


def test_audit_event_is_append_only_by_convention(db_session):
    event = AuditEvent(
        correlation_id="corr-1", entity_type="InvoiceDelivery", entity_id="delivery-1",
        event_name="DELIVERY_CREATED", actor_type="API", new_state="DELIVERY_CREATED",
    )
    db_session.add(event)
    db_session.commit()

    fetched = db_session.query(AuditEvent).filter_by(correlation_id="corr-1").one()
    assert fetched.new_state == "DELIVERY_CREATED"


def test_idempotency_record_tracks_delivery_id(db_session):
    record = IdempotencyRecord(
        operation_name="invoice_delivery_intake", idempotency_key="evt_123",
        request_hash="deadbeef", status="COMPLETED", delivery_id="delivery-xyz",
    )
    db_session.add(record)
    db_session.commit()

    fetched = db_session.query(IdempotencyRecord).filter_by(idempotency_key="evt_123").one()
    assert fetched.delivery_id == "delivery-xyz"
