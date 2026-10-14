"""Email/WhatsApp provider delivery-status webhooks (spec §9, §10, §14).
Each route verifies the provider's signature before trusting anything in
the payload, then updates the matching DeliveryAttempt by provider
message ID.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.delivery_attempt import DeliveryAttempt
from app.models.invoice_delivery import InvoiceDelivery
from app.services.audit.service import record_event
from app.services.email.factory import get_email_provider
from app.services.whatsapp.factory import get_whatsapp_provider
from app.workflows.delivery_workflow import recompute_delivery_status

router = APIRouter(prefix="/api/v1/webhooks", tags=["provider-webhooks"])


@router.post("/email")
async def email_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    raw_body = await request.body()
    provider = get_email_provider(settings)
    if not provider.verify_webhook(headers=dict(request.headers), raw_body=raw_body):
        raise HTTPException(status_code=401, detail="webhook signature verification failed")

    event = await request.json()
    event_type = event.get("event_type", "delivered")
    if event_type == "bounced":
        normalized = provider.handle_bounce_event(event)
    elif event_type == "complaint":
        normalized = provider.handle_complaint_event(event)
    else:
        normalized = provider.handle_delivery_event(event)

    attempt = db.query(DeliveryAttempt).filter_by(provider_message_id=normalized.message_id).one_or_none()
    if attempt is None:
        return {"status": "ignored", "reason": "no matching attempt for provider_message_id"}

    _apply_email_status(db, attempt, normalized)
    return {"status": "processed"}


def _apply_email_status(db: Session, attempt: DeliveryAttempt, normalized) -> None:
    status_map = {"delivered": "DELIVERED", "bounced": "BOUNCED", "complaint": "BOUNCED", "failed": "FAILED"}
    new_status = status_map.get(normalized.event_type, attempt.status)
    previous = attempt.status
    attempt.status = new_status
    attempt.provider_response_safe_json = normalized.detail_safe
    if new_status == "DELIVERED":
        attempt.delivered_at = datetime.now(timezone.utc)
    if new_status in {"BOUNCED", "FAILED"}:
        attempt.failed_at = datetime.now(timezone.utc)
        attempt.error_code = attempt.error_code or normalized.event_type
    db.add(attempt)
    db.commit()

    delivery = db.query(InvoiceDelivery).filter_by(id=attempt.delivery_id).one()
    record_event(
        db, correlation_id=delivery.correlation_id, entity_type="DeliveryAttempt", entity_id=attempt.id,
        event_name=f"EMAIL_{normalized.event_type.upper()}", actor_type="EMAIL_PROVIDER",
        previous_state=previous, new_state=new_status, safe_payload=normalized.detail_safe,
    )
    recompute_delivery_status(db, delivery)


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    raw_body = await request.body()
    provider = get_whatsapp_provider(settings)
    headers = dict(request.headers)
    headers.setdefault("X-Webhook-Url", str(request.url))
    if not provider.verify_webhook(headers=headers, raw_body=raw_body):
        raise HTTPException(status_code=401, detail="webhook signature verification failed")

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        event = await request.json()
    else:
        form = await request.form()
        event = dict(form)

    normalized = provider.handle_status_event(event)

    attempt = db.query(DeliveryAttempt).filter_by(provider_message_id=normalized.message_id).one_or_none()
    if attempt is None:
        return {"status": "ignored", "reason": "no matching attempt for provider_message_id"}

    _apply_whatsapp_status(db, attempt, normalized)
    return {"status": "processed"}


def _apply_whatsapp_status(db: Session, attempt: DeliveryAttempt, normalized) -> None:
    status_map = {"accepted": "SENT", "sent": "SENT", "delivered": "DELIVERED", "read": "READ", "failed": "FAILED"}
    new_status = status_map.get(normalized.status, attempt.status)
    previous = attempt.status
    attempt.status = new_status
    attempt.provider_response_safe_json = normalized.detail_safe
    if new_status == "DELIVERED":
        attempt.delivered_at = datetime.now(timezone.utc)
    if new_status == "FAILED":
        attempt.failed_at = datetime.now(timezone.utc)
        attempt.error_code = attempt.error_code or "provider_failed"
    db.add(attempt)
    db.commit()

    delivery = db.query(InvoiceDelivery).filter_by(id=attempt.delivery_id).one()
    record_event(
        db, correlation_id=delivery.correlation_id, entity_type="DeliveryAttempt", entity_id=attempt.id,
        event_name=f"WHATSAPP_{normalized.status.upper()}", actor_type="WHATSAPP_PROVIDER",
        previous_state=previous, new_state=new_status, safe_payload=normalized.detail_safe,
    )
    recompute_delivery_status(db, delivery)
