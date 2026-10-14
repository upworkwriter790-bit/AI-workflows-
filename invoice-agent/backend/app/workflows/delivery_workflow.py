"""Invoice-delivery workflow — spec §8. Orchestrates DeliveryAttempt rows
for each requested channel, dispatches to the configured email/WhatsApp
providers, and rolls per-attempt status up into InvoiceDelivery.status.

Design decision (documented, not hidden): the spec's fixed status enum
has no single "every requested channel failed" value for a multi-channel
delivery. Rule 5 only specifies PARTIALLY_DELIVERED for a mixed
success/failure outcome. This module uses EMAIL_FAILED/WHATSAPP_FAILED
as the overall status only when that is the single requested channel;
for a multi-channel delivery where every channel ultimately fails, it
falls back to PARTIALLY_DELIVERED as the closest named state — the exact
per-channel failure is always visible on each DeliveryAttempt row
regardless of what the rollup status says.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.delivery_attempt import DeliveryAttempt
from app.models.invoice_delivery import InvoiceDelivery
from app.models.invoice_document import InvoiceDocument
from app.schemas.delivery_request import InvoiceDeliveryRequestFields
from app.services.audit.service import record_event
from app.services.email.base import EmailSendPayload
from app.services.email.factory import get_email_provider
from app.services.email.templates import build_body, build_subject
from app.services.provider_errors import PermanentProviderError, TransientProviderError
from app.services.secure_links.service import create_link
from app.services.storage.factory import get_storage_adapter
from app.services.whatsapp.base import WhatsAppSendPayload
from app.services.whatsapp.factory import get_whatsapp_provider

_SUCCESS_STATUSES = {"SENT", "DELIVERED", "READ"}


@dataclass
class DispatchOutcome:
    should_retry: bool
    retry_after_seconds: int | None = None


def create_delivery(
    db: Session,
    *,
    document: InvoiceDocument,
    fields: InvoiceDeliveryRequestFields,
    correlation_id: str,
) -> InvoiceDelivery:
    """Creates the delivery as a human-reviewable DRAFT. No DeliveryAttempt
    row is created and nothing is dispatched yet — see `approve_delivery()`.
    This is a deliberate gate (added on top of the original spec): every
    delivery, uploaded or generated, waits for an authorized human
    approval before anything is sent by email or WhatsApp.
    """
    delivery = InvoiceDelivery(
        document_id=document.id,
        recipient_name=fields.recipient_name,
        recipient_email=fields.recipient_email,
        recipient_phone=fields.recipient_phone,
        requested_channels_json=fields.requested_channels,
        external_reference=fields.external_reference,
        invoice_number=fields.invoice_number,
        attach_pdf_to_email=fields.attach_pdf_to_email,
        include_download_link=fields.include_download_link,
        send_whatsapp_notification=fields.send_whatsapp_notification,
        status="DRAFT",
        idempotency_key=fields.idempotency_key,
        correlation_id=correlation_id,
    )
    db.add(delivery)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="InvoiceDelivery", entity_id=delivery.id,
        event_name="DRAFT_CREATED", actor_type="API", new_state="DRAFT",
        safe_payload={"requested_channels": fields.requested_channels},
    )
    return delivery


def approve_delivery(db: Session, delivery: InvoiceDelivery, *, approved_by_user_id: str) -> InvoiceDelivery:
    """The human-approval step: creates one DeliveryAttempt per requested
    channel and moves the delivery to QUEUED. The caller (API layer) is
    responsible for then enqueuing the actual Celery dispatch tasks —
    this function only prepares the rows, matching the pattern the rest
    of the workflow already uses.
    """
    if delivery.status != "DRAFT":
        raise DeliveryNotDraftError(delivery.id, delivery.status)

    for channel in delivery.requested_channels_json:
        attempt = DeliveryAttempt(delivery_id=delivery.id, channel=channel.upper(), attempt_number=1, status="QUEUED")
        db.add(attempt)
    delivery.status = "QUEUED"
    db.add(delivery)
    db.commit()
    record_event(
        db, correlation_id=delivery.correlation_id, entity_type="InvoiceDelivery", entity_id=delivery.id,
        event_name="DELIVERY_APPROVED", actor_type="USER", actor_id=approved_by_user_id,
        previous_state="DRAFT", new_state="QUEUED",
    )
    return delivery


class DeliveryNotDraftError(Exception):
    def __init__(self, delivery_id: str, current_status: str) -> None:
        self.delivery_id = delivery_id
        self.current_status = current_status
        super().__init__(f"delivery {delivery_id} is not in DRAFT (current status: {current_status})")


def recompute_delivery_status(db: Session, delivery: InvoiceDelivery) -> None:
    attempts = db.query(DeliveryAttempt).filter_by(delivery_id=delivery.id).all()
    latest_by_channel: dict[str, DeliveryAttempt] = {}
    for attempt in attempts:
        current = latest_by_channel.get(attempt.channel)
        if current is None or attempt.attempt_number >= current.attempt_number:
            latest_by_channel[attempt.channel] = attempt

    requested = {c.upper() for c in delivery.requested_channels_json}
    succeeded = {ch for ch, a in latest_by_channel.items() if ch in requested and a.status in _SUCCESS_STATUSES}
    failed = {ch for ch, a in latest_by_channel.items() if ch in requested and a.status == "FAILED"}
    pending = requested - succeeded - failed

    previous = delivery.status
    if pending:
        retrying = any(latest_by_channel[ch].status == "RETRYING" for ch in pending if ch in latest_by_channel)
        new_status = "RETRY_SCHEDULED" if retrying else delivery.status
    elif succeeded == requested:
        new_status = "COMPLETED"
    elif succeeded and failed:
        new_status = "PARTIALLY_DELIVERED"
    elif failed == requested:
        if len(requested) == 1 and "EMAIL" in requested:
            new_status = "EMAIL_FAILED"
        elif len(requested) == 1 and "WHATSAPP" in requested:
            new_status = "WHATSAPP_FAILED"
        else:
            new_status = "PARTIALLY_DELIVERED"
    else:
        new_status = delivery.status

    if new_status != previous:
        delivery.status = new_status
        db.add(delivery)
        db.commit()
        record_event(
            db, correlation_id=delivery.correlation_id, entity_type="InvoiceDelivery", entity_id=delivery.id,
            event_name="STATUS_RECOMPUTED", actor_type="SYSTEM", previous_state=previous, new_state=new_status,
        )


def _ensure_secure_link(db: Session, settings: Settings, delivery: InvoiceDelivery) -> str | None:
    link = create_link(
        db,
        document_id=delivery.document_id,
        delivery_id=delivery.id,
        expiry_days=settings.secure_link_expiry_days,
        max_downloads=settings.secure_link_max_downloads,
    )
    return f"{settings.app_base_url}/d/{link.token}"


def dispatch_email_attempt(
    db: Session,
    settings: Settings,
    attempt: DeliveryAttempt,
    *,
    attach_pdf: bool,
    include_download_link: bool,
) -> DispatchOutcome:
    delivery = db.query(InvoiceDelivery).filter_by(id=attempt.delivery_id).one()
    document = db.query(InvoiceDocument).filter_by(id=delivery.document_id).one()

    secure_link = _ensure_secure_link(db, settings, delivery) if include_download_link else None
    pdf_bytes = None
    if attach_pdf:
        storage = get_storage_adapter(settings)
        pdf_bytes = storage.read(document.storage_key)

    subject = build_subject(delivery.invoice_number or delivery.external_reference)
    body = build_body(
        recipient_name=delivery.recipient_name,
        support_email=settings.support_email or "",
        company_legal_name=settings.company_legal_name or "",
        secure_link=secure_link,
    )

    provider = get_email_provider(settings)
    attempt.status = "SENDING"
    db.add(attempt)
    db.commit()

    try:
        message_id = provider.send_invoice_email(
            EmailSendPayload(
                to_email=delivery.recipient_email,
                to_name=delivery.recipient_name,
                subject=subject,
                body_text=body,
                pdf_attachment_bytes=pdf_bytes,
                pdf_attachment_filename=document.sanitized_filename,
                idempotency_key=f"{delivery.id}:email:{attempt.attempt_number}",
            )
        )
    except (TransientProviderError, PermanentProviderError) as exc:
        return _handle_dispatch_failure(db, settings, attempt, exc)

    attempt.status = "SENT"
    attempt.provider = provider.name
    attempt.provider_message_id = message_id
    attempt.sent_at = datetime.now(UTC)
    db.add(attempt)
    db.commit()
    record_event(
        db, correlation_id=delivery.correlation_id, entity_type="DeliveryAttempt", entity_id=attempt.id,
        event_name="EMAIL_SENT", actor_type="SYSTEM", new_state="SENT",
        safe_payload={"provider_message_id": message_id},
    )
    recompute_delivery_status(db, delivery)
    return DispatchOutcome(should_retry=False)


def dispatch_whatsapp_attempt(
    db: Session,
    settings: Settings,
    attempt: DeliveryAttempt,
    *,
    include_download_link: bool,
) -> DispatchOutcome:
    delivery = db.query(InvoiceDelivery).filter_by(id=attempt.delivery_id).one()
    secure_link = _ensure_secure_link(db, settings, delivery) if include_download_link else None

    try:
        provider = get_whatsapp_provider(settings)
    except (RuntimeError, NotImplementedError) as exc:
        return _mark_configuration_failed(db, attempt, delivery, exc)

    attempt.status = "SENDING"
    db.add(attempt)
    db.commit()

    try:
        message_id = provider.send_invoice_notification(
            WhatsAppSendPayload(
                to_phone_e164=delivery.recipient_phone,
                recipient_name=delivery.recipient_name,
                invoice_number_or_reference=delivery.invoice_number or delivery.external_reference,
                secure_link=secure_link,
                idempotency_key=f"{delivery.id}:whatsapp:{attempt.attempt_number}",
            )
        )
    except (TransientProviderError, PermanentProviderError) as exc:
        return _handle_dispatch_failure(db, settings, attempt, exc)

    attempt.status = "SENT"
    attempt.provider = provider.name
    attempt.provider_message_id = message_id
    attempt.sent_at = datetime.now(UTC)
    db.add(attempt)
    db.commit()
    record_event(
        db, correlation_id=delivery.correlation_id, entity_type="DeliveryAttempt", entity_id=attempt.id,
        event_name="WHATSAPP_SENT", actor_type="SYSTEM", new_state="SENT",
        safe_payload={"provider_message_id": message_id},
    )
    recompute_delivery_status(db, delivery)
    return DispatchOutcome(should_retry=False)


def _mark_configuration_failed(
    db: Session, attempt: DeliveryAttempt, delivery: InvoiceDelivery, exc: Exception
) -> DispatchOutcome:
    """Per spec §10: an unconfigured WhatsApp channel marks that channel
    configuration-failed and must not block email delivery.
    """
    attempt.status = "FAILED"
    attempt.error_code = "configuration_failed"
    attempt.error_message_safe = "WhatsApp provider is not configured"
    attempt.failed_at = datetime.now(UTC)
    db.add(attempt)
    db.commit()
    record_event(
        db, correlation_id=delivery.correlation_id, entity_type="DeliveryAttempt", entity_id=attempt.id,
        event_name="WHATSAPP_CONFIGURATION_FAILED", actor_type="SYSTEM", new_state="FAILED",
        safe_payload={"error_code": "configuration_failed"},
    )
    recompute_delivery_status(db, delivery)
    return DispatchOutcome(should_retry=False)


def _handle_dispatch_failure(
    db: Session, settings: Settings, attempt: DeliveryAttempt, exc: Exception
) -> DispatchOutcome:
    delivery = db.query(InvoiceDelivery).filter_by(id=attempt.delivery_id).one()
    error_code = getattr(exc, "error_code", "unknown_error")

    if isinstance(exc, TransientProviderError) and attempt.attempt_number < settings.retry_max_attempts:
        schedule = settings.retry_schedule_seconds
        delay_index = min(attempt.attempt_number - 1, len(schedule) - 1)
        retry_after_seconds = schedule[delay_index]
        next_attempt_number = attempt.attempt_number + 1

        attempt.status = "RETRYING"
        attempt.error_code = error_code
        attempt.error_message_safe = str(exc)[:500]
        attempt.attempt_number = next_attempt_number
        db.add(attempt)
        db.commit()
        record_event(
            db, correlation_id=delivery.correlation_id, entity_type="DeliveryAttempt", entity_id=attempt.id,
            event_name="RETRY_SCHEDULED", actor_type="SYSTEM", new_state="RETRYING",
            safe_payload={"error_code": error_code, "next_attempt_number": next_attempt_number,
                          "retry_after_seconds": retry_after_seconds},
        )
        recompute_delivery_status(db, delivery)
        return DispatchOutcome(should_retry=True, retry_after_seconds=retry_after_seconds)

    attempt.status = "FAILED"
    attempt.error_code = error_code
    attempt.error_message_safe = str(exc)[:500]
    attempt.failed_at = datetime.now(UTC)
    db.add(attempt)
    db.commit()
    event_name = "EMAIL_FAILED" if attempt.channel == "EMAIL" else "WHATSAPP_FAILED"
    record_event(
        db, correlation_id=delivery.correlation_id, entity_type="DeliveryAttempt", entity_id=attempt.id,
        event_name=event_name, actor_type="SYSTEM", new_state="FAILED",
        safe_payload={"error_code": error_code, "permanent": isinstance(exc, PermanentProviderError)},
    )
    recompute_delivery_status(db, delivery)
    return DispatchOutcome(should_retry=False)


def create_resend_attempt(
    db: Session, *, delivery: InvoiceDelivery, channel: str, reason: str, requested_by_user_id: str
) -> DeliveryAttempt:
    """A manual resend creates a new DeliveryAttempt, never a new
    InvoiceDocument or InvoiceDelivery (spec §8 rule 8, §13.3).
    """
    channel = channel.upper()
    previous = (
        db.query(DeliveryAttempt)
        .filter_by(delivery_id=delivery.id, channel=channel)
        .order_by(DeliveryAttempt.attempt_number.desc())
        .first()
    )
    next_number = (previous.attempt_number + 1) if previous else 1

    attempt = DeliveryAttempt(
        delivery_id=delivery.id,
        channel=channel,
        attempt_number=next_number,
        is_resend=True,
        resend_reason=reason,
        resend_requested_by_user_id=requested_by_user_id,
        status="QUEUED",
    )
    db.add(attempt)
    db.commit()
    record_event(
        db, correlation_id=delivery.correlation_id, entity_type="DeliveryAttempt", entity_id=attempt.id,
        event_name="MANUAL_RESEND_REQUESTED", actor_type="USER", actor_id=requested_by_user_id,
        new_state="QUEUED", safe_payload={"channel": channel, "reason": reason},
    )
    return attempt
