"""Invoice-delivery API routes (spec §6, §14). The intake endpoint never
inspects, interprets, extracts, authenticates, or edits invoice content —
it validates shape/size/type only, stores the file, and queues delivery.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import InternalUser, require_role
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.delivery_attempt import DeliveryAttempt
from app.models.invoice_delivery import InvoiceDelivery
from app.models.invoice_document import InvoiceDocument
from app.schemas.delivery_request import InvoiceDeliveryRequestFields
from app.services.audit.service import record_event
from app.services.file_validation import (
    FileValidationError,
    PhoneValidationError,
    validate_e164_phone,
    validate_pdf_upload,
)
from app.services.idempotency import ReservationStatus, hash_request_body, mark_completed, reserve
from app.services.storage.factory import get_storage_adapter
from app.workflows.delivery_workflow import create_delivery, create_resend_attempt

router = APIRouter(prefix="/api/v1/invoice-deliveries", tags=["invoice-deliveries"])

IDEMPOTENCY_OPERATION = "invoice_delivery_intake"


def _mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    masked_local = local[0] + "***" if local else "***"
    return f"{masked_local}@{domain}"


def _mask_phone(phone: str | None) -> str | None:
    if not phone or len(phone) < 4:
        return phone
    return f"{phone[:3]}{'*' * (len(phone) - 6)}{phone[-3:]}"


def _delivery_response(delivery: InvoiceDelivery) -> dict:
    return {
        "delivery_id": delivery.id,
        "correlation_id": delivery.correlation_id,
        "status": delivery.status,
        "requested_channels": delivery.requested_channels_json,
        "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
    }


@router.post("", status_code=202)
async def create_invoice_delivery(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER"))],
    invoice_file: UploadFile,
    recipient_name: Annotated[str, Form()],
    requested_channels: Annotated[list[str], Form()],
    idempotency_key: Annotated[str, Form()],
    recipient_email: Annotated[str | None, Form()] = None,
    recipient_phone: Annotated[str | None, Form()] = None,
    external_reference: Annotated[str | None, Form()] = None,
    invoice_number: Annotated[str | None, Form()] = None,
    source: Annotated[str, Form()] = "INTERNAL_UPLOAD",
    notes: Annotated[str | None, Form()] = None,
    attach_pdf_to_email: Annotated[bool, Form()] = True,
    include_download_link: Annotated[bool, Form()] = True,
    send_whatsapp_notification: Annotated[bool, Form()] = True,
) -> dict:
    try:
        fields = InvoiceDeliveryRequestFields(
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            requested_channels=requested_channels,
            idempotency_key=idempotency_key,
            external_reference=external_reference,
            invoice_number=invoice_number,
            source=source,
            notes=notes,
            attach_pdf_to_email=attach_pdf_to_email,
            include_download_link=include_download_link,
            send_whatsapp_notification=send_whatsapp_notification,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from exc

    contact_errors = fields.require_channel_contact_info()
    if contact_errors:
        raise HTTPException(status_code=400, detail=contact_errors)

    if "whatsapp" in fields.requested_channels:
        try:
            fields.recipient_phone = validate_e164_phone(fields.recipient_phone)
        except PhoneValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    file_bytes = await invoice_file.read()
    try:
        sanitized_filename = validate_pdf_upload(
            filename=invoice_file.filename or "invoice.pdf",
            content_type=invoice_file.content_type,
            data=file_bytes,
            max_bytes=settings.max_file_size_bytes,
        )
    except FileValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    request_hash = hash_request_body(file_bytes + fields.model_dump_json().encode("utf-8"))
    reservation = reserve(
        db, operation_name=IDEMPOTENCY_OPERATION, idempotency_key=fields.idempotency_key, request_hash=request_hash
    )
    if reservation.status is ReservationStatus.DUPLICATE:
        if reservation.record.delivery_id:
            existing = db.query(InvoiceDelivery).filter_by(id=reservation.record.delivery_id).one_or_none()
            if existing is not None:
                return _delivery_response(existing)
        raise HTTPException(status_code=409, detail="idempotency_key is already being processed")

    sha256 = hashlib.sha256(file_bytes).hexdigest()
    document_id = str(uuid.uuid4())
    storage_key = f"invoice-documents/{document_id}/{sanitized_filename}"
    storage = get_storage_adapter(settings)
    storage.save(storage_key, file_bytes, content_type="application/pdf")

    document = InvoiceDocument(
        id=document_id,
        original_filename=invoice_file.filename or sanitized_filename,
        sanitized_filename=sanitized_filename,
        mime_type="application/pdf",
        byte_size=len(file_bytes),
        sha256=sha256,
        storage_key=storage_key,
        uploaded_by_user_id=user.id,
        external_reference=fields.external_reference,
        invoice_number=fields.invoice_number,
        source=fields.source,
    )
    db.add(document)
    db.commit()

    correlation_id = f"corr_{uuid.uuid4().hex[:16]}"
    record_event(
        db, correlation_id=correlation_id, entity_type="InvoiceDocument", entity_id=document.id,
        event_name="FILE_STORED", actor_type="USER", actor_id=user.id,
        safe_payload={"sha256": sha256, "byte_size": document.byte_size},
    )

    delivery = create_delivery(db, document=document, fields=fields, correlation_id=correlation_id)
    delivery.created_by_user_id = user.id
    db.add(delivery)
    db.commit()

    mark_completed(db, reservation.record, response_reference=delivery.id, delivery_id=delivery.id)

    from app.tasks.delivery_tasks import send_email_attempt_task, send_whatsapp_attempt_task

    for attempt in db.query(DeliveryAttempt).filter_by(delivery_id=delivery.id).all():
        if attempt.channel == "EMAIL":
            send_email_attempt_task.delay(
                attempt.id, attach_pdf=fields.attach_pdf_to_email, include_download_link=fields.include_download_link
            )
        elif attempt.channel == "WHATSAPP" and fields.send_whatsapp_notification:
            send_whatsapp_attempt_task.delay(attempt.id, include_download_link=fields.include_download_link)

    return _delivery_response(delivery)


@router.get("")
def list_invoice_deliveries(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER", "DELIVERY_VIEWER"))],
    status_filter: str | None = None,
    source: str | None = None,
    channel: str | None = None,
    search: str | None = None,
) -> dict:
    query = db.query(InvoiceDelivery)
    if status_filter:
        query = query.filter(InvoiceDelivery.status == status_filter)
    if search:
        query = query.filter(
            (InvoiceDelivery.id == search)
            | (InvoiceDelivery.external_reference == search)
            | (InvoiceDelivery.invoice_number == search)
            | (InvoiceDelivery.recipient_email == search)
            | (InvoiceDelivery.recipient_phone == search)
        )

    results = []
    for delivery in query.order_by(InvoiceDelivery.created_at.desc()).all():
        if channel and channel.lower() not in [c.lower() for c in delivery.requested_channels_json]:
            continue
        results.append(
            {
                "delivery_id": delivery.id,
                "external_reference": delivery.external_reference,
                "invoice_number": delivery.invoice_number,
                "recipient_name": delivery.recipient_name,
                "recipient_email": _mask_email(delivery.recipient_email),
                "recipient_phone": _mask_phone(delivery.recipient_phone),
                "requested_channels": delivery.requested_channels_json,
                "status": delivery.status,
                "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
            }
        )
    return {"deliveries": results, "count": len(results)}


@router.get("/{delivery_id}")
def get_invoice_delivery(
    delivery_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER", "DELIVERY_VIEWER"))],
) -> dict:
    delivery = db.query(InvoiceDelivery).filter_by(id=delivery_id).one_or_none()
    if delivery is None:
        raise HTTPException(status_code=404, detail="delivery not found")

    attempts = db.query(DeliveryAttempt).filter_by(delivery_id=delivery.id).order_by(DeliveryAttempt.created_at).all()
    from app.services.audit.service import get_audit_trail

    timeline = get_audit_trail(db, entity_type="InvoiceDelivery", entity_id=delivery.id) + get_audit_trail(
        db, entity_type="InvoiceDocument", entity_id=delivery.document_id
    )
    for attempt in attempts:
        timeline += get_audit_trail(db, entity_type="DeliveryAttempt", entity_id=attempt.id)
    timeline.sort(key=lambda e: e.created_at)

    return {
        "delivery_id": delivery.id,
        "correlation_id": delivery.correlation_id,
        "status": delivery.status,
        "recipient_name": delivery.recipient_name,
        "recipient_email": delivery.recipient_email,
        "recipient_phone": delivery.recipient_phone,
        "requested_channels": delivery.requested_channels_json,
        "external_reference": delivery.external_reference,
        "invoice_number": delivery.invoice_number,
        "document_id": delivery.document_id,
        "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
        "attempts": [
            {
                "attempt_id": a.id,
                "channel": a.channel,
                "attempt_number": a.attempt_number,
                "is_resend": a.is_resend,
                "status": a.status,
                "provider": a.provider,
                "provider_message_id": a.provider_message_id,
                "error_code": a.error_code,
                "error_message_safe": a.error_message_safe,
                "sent_at": a.sent_at.isoformat() if a.sent_at else None,
                "delivered_at": a.delivered_at.isoformat() if a.delivered_at else None,
                "failed_at": a.failed_at.isoformat() if a.failed_at else None,
            }
            for a in attempts
        ],
        "audit_timeline": [
            {
                "event_name": e.event_name,
                "actor_type": e.actor_type,
                "actor_id": e.actor_id,
                "previous_state": e.previous_state,
                "new_state": e.new_state,
                "safe_payload": e.safe_payload_json,
                "created_at": e.created_at.isoformat(),
            }
            for e in timeline
        ],
    }


@router.post("/{delivery_id}/resend")
def resend_invoice_delivery(
    delivery_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER"))],
    channels: Annotated[list[str], Form()],
    reason: Annotated[str, Form(min_length=1)],
) -> dict:
    delivery = db.query(InvoiceDelivery).filter_by(id=delivery_id).one_or_none()
    if delivery is None:
        raise HTTPException(status_code=404, detail="delivery not found")

    from app.tasks.delivery_tasks import send_email_attempt_task, send_whatsapp_attempt_task

    created_attempts = []
    for channel in channels:
        channel_upper = channel.strip().upper()
        if channel_upper not in {"EMAIL", "WHATSAPP"}:
            raise HTTPException(status_code=400, detail=f"unknown channel: {channel}")
        attempt = create_resend_attempt(
            db, delivery=delivery, channel=channel_upper, reason=reason, requested_by_user_id=user.id
        )
        created_attempts.append(attempt.id)
        if channel_upper == "EMAIL":
            send_email_attempt_task.delay(attempt.id, attach_pdf=True, include_download_link=True)
        else:
            send_whatsapp_attempt_task.delay(attempt.id, include_download_link=True)

    return {"delivery_id": delivery.id, "new_attempt_ids": created_attempts, "status": "RESEND_QUEUED"}


@router.post("/{delivery_id}/cancel")
def cancel_invoice_delivery(
    delivery_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER"))],
) -> dict:
    delivery = db.query(InvoiceDelivery).filter_by(id=delivery_id).one_or_none()
    if delivery is None:
        raise HTTPException(status_code=404, detail="delivery not found")

    if delivery.status in {"COMPLETED", "CANCELLED"}:
        raise HTTPException(status_code=409, detail=f"delivery cannot be cancelled from status {delivery.status}")

    previous = delivery.status
    delivery.status = "CANCELLED"
    db.add(delivery)
    db.commit()
    record_event(
        db, correlation_id=delivery.correlation_id, entity_type="InvoiceDelivery", entity_id=delivery.id,
        event_name="DELIVERY_CANCELLED", actor_type="USER", actor_id=user.id,
        previous_state=previous, new_state="CANCELLED",
    )
    return {"delivery_id": delivery.id, "status": "CANCELLED"}


@router.post("/{delivery_id}/secure-link/reissue")
def reissue_secure_link(
    delivery_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER"))],
) -> dict:
    delivery = db.query(InvoiceDelivery).filter_by(id=delivery_id).one_or_none()
    if delivery is None:
        raise HTTPException(status_code=404, detail="delivery not found")

    from app.models.secure_download_link import SecureDownloadLink
    from app.services.secure_links.service import create_link, revoke_link

    active_links = (
        db.query(SecureDownloadLink)
        .filter_by(delivery_id=delivery.id, revoked_at=None)
        .all()
    )
    for link in active_links:
        revoke_link(db, link)
        record_event(
            db, correlation_id=delivery.correlation_id, entity_type="SecureDownloadLink", entity_id=link.id,
            event_name="SECURE_LINK_REVOKED", actor_type="USER", actor_id=user.id, new_state="REVOKED",
        )

    new_link = create_link(
        db,
        document_id=delivery.document_id,
        delivery_id=delivery.id,
        expiry_days=settings.secure_link_expiry_days,
        max_downloads=settings.secure_link_max_downloads,
    )
    record_event(
        db, correlation_id=delivery.correlation_id, entity_type="SecureDownloadLink", entity_id=new_link.record.id,
        event_name="SECURE_LINK_REISSUED", actor_type="USER", actor_id=user.id, new_state="ACTIVE",
    )
    return {
        "delivery_id": delivery.id,
        "download_url": f"{settings.app_base_url}/d/{new_link.token}",
        "expires_at": new_link.record.expires_at.isoformat(),
        "max_downloads": new_link.record.max_downloads,
    }
