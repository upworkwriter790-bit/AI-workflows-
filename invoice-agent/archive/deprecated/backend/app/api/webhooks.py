"""CRM `order.paid` webhook — spec §8. HMAC-signed, timestamp-bounded,
idempotency-keyed, schema-validated, and acknowledged immediately (202)
before any workflow processing runs — processing is handed off to Celery
so this endpoint never blocks on GST calc / PDF rendering / storage.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import verify_signature
from app.db.session import get_db
from app.models.customer import Customer
from app.models.order import Order
from app.schemas.order_webhook import OrderPaidWebhookPayload
from app.services.audit.service import record_event
from app.services.idempotency import (
    ReservationStatus,
    hash_request_body,
    mark_completed,
    mark_failed,
    reserve,
)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

IDEMPOTENCY_OPERATION = "order_paid_webhook"


def _upsert_customer(db: Session, payload: OrderPaidWebhookPayload) -> Customer:
    customer = db.query(Customer).filter_by(crm_customer_id=payload.customer_id).one_or_none()
    billing = payload.customer.billing_address
    if customer is None:
        customer = Customer(
            crm_customer_id=payload.customer_id,
            legal_name=payload.customer.name,
            email=payload.customer.email,
            phone=payload.customer.phone,
            gstin=payload.customer.gstin,
            billing_address_json=billing.model_dump(mode="json"),
            shipping_address_json=(
                payload.customer.shipping_address.model_dump(mode="json")
                if payload.customer.shipping_address
                else {}
            ),
            state_name=billing.state,
            state_code=billing.state_code,
        )
        db.add(customer)
        db.commit()
    return customer


@router.post("/crm/order-paid", status_code=202)
async def crm_order_paid(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_signature: Annotated[str | None, Header(alias="X-Signature")] = None,
    x_timestamp: Annotated[str | None, Header(alias="X-Timestamp")] = None,
) -> dict:
    raw_body = await request.body()

    if not x_signature or not x_timestamp:
        raise HTTPException(status_code=401, detail="missing signature headers")

    ok, reason = verify_signature(settings.crm_webhook_hmac_secret, x_timestamp, raw_body, x_signature)
    if not ok:
        raise HTTPException(status_code=401, detail=reason or "invalid signature")

    try:
        payload = OrderPaidWebhookPayload.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from exc

    request_hash = hash_request_body(raw_body)
    reservation = reserve(
        db, operation_name=IDEMPOTENCY_OPERATION, idempotency_key=payload.event_id, request_hash=request_hash
    )
    if reservation.status is ReservationStatus.DUPLICATE:
        raise HTTPException(status_code=409, detail="event already processing or completed")

    existing_order = db.query(Order).filter_by(crm_order_id=payload.order_id).one_or_none()
    if existing_order is not None:
        mark_failed(db, reservation.record)
        raise HTTPException(status_code=409, detail="order already processed")

    customer = _upsert_customer(db, payload)

    order = Order(
        crm_order_id=payload.order_id,
        customer_id=customer.id,
        payment_status=payload.payment_status,
        payment_reference=payload.payment_reference,
        paid_at=payload.occurred_at,
        currency=payload.currency,
        subtotal=payload.pricing.subtotal,
        discount_total=payload.pricing.discount_total,
        tax_total=payload.pricing.tax_total,
        grand_total=payload.pricing.grand_total,
        order_snapshot_json=payload.model_dump(mode="json"),
        idempotency_key=payload.event_id,
    )
    db.add(order)
    db.commit()

    record_event(
        db,
        correlation_id=order.crm_order_id,
        entity_type="Order",
        entity_id=order.id,
        event_name="PAID_ORDER_WEBHOOK_ACCEPTED",
        actor_type="CRM",
        new_state="PAID_ORDER_RECEIVED",
        safe_payload={"event_id": payload.event_id, "order_id": order.crm_order_id},
    )

    mark_completed(db, reservation.record, response_reference=order.id)

    from app.tasks.order_tasks import process_paid_order_task

    process_paid_order_task.delay(order.id)

    return {"status": "accepted", "order_id": order.id, "correlation_id": order.crm_order_id}
