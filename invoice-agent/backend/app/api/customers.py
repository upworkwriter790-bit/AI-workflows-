"""Lightweight internal customer directory (spec §8/§3) — not a CRM
integration. Exists only so Quick Create can find a returning
customer's billing details by exact email/phone match. Explicit
create/update only — nothing here is ever written automatically from
AI output or a receipt upload (spec §8 rule: "show 'Save these updated
details?' with explicit confirmation").
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import InternalUser, require_role
from app.db.session import get_db
from app.models.customer import Customer
from app.services.audit.service import record_event

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


class BillingAddress(BaseModel):
    model_config = ConfigDict(extra="allow")

    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    state_code: str | None = None
    postal_code: str | None = None
    country: str | None = "India"


class CustomerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    legal_name: str | None = None
    email: str | None = None
    phone: str | None = None
    gstin: str | None = None
    billing_address: dict | None = None
    shipping_address: dict | None = None
    state_name: str | None = None
    state_code: str | None = None
    preferred_delivery_channels: list[str] = []


def _serialize(c: Customer) -> dict:
    return {
        "id": c.id,
        "display_name": c.display_name,
        "legal_name": c.legal_name,
        "email": c.email,
        "phone": c.phone,
        "gstin": c.gstin,
        "billing_address": c.billing_address_json,
        "shipping_address": c.shipping_address_json,
        "state_name": c.state_name,
        "state_code": c.state_code,
        "preferred_delivery_channels": c.preferred_delivery_channels_json or [],
        "source": c.source,
        "verification_status": c.verification_status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("")
def list_customers(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR", "INVOICE_APPROVER", "DELIVERY_MANAGER", "DELIVERY_VIEWER"))],
    search: str | None = None,
) -> dict:
    query = db.query(Customer)
    if search:
        query = query.filter(
            (Customer.display_name.ilike(f"%{search}%"))
            | (Customer.email == search)
            | (Customer.phone == search)
        )
    return {"customers": [_serialize(c) for c in query.order_by(Customer.display_name).all()]}


@router.post("", status_code=201)
def create_customer(
    payload: CustomerRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR", "INVOICE_APPROVER"))],
) -> dict:
    customer = Customer(
        display_name=payload.display_name,
        legal_name=payload.legal_name,
        email=payload.email.strip().lower() if payload.email else None,
        phone=payload.phone,
        gstin=payload.gstin,
        billing_address_json=payload.billing_address,
        shipping_address_json=payload.shipping_address,
        state_name=payload.state_name,
        state_code=payload.state_code,
        preferred_delivery_channels_json=payload.preferred_delivery_channels,
        source="MANUAL",
        created_by_user_id=user.id,
    )
    db.add(customer)
    db.commit()
    record_event(
        db, correlation_id=customer.id, entity_type="Customer", entity_id=customer.id,
        event_name="CUSTOMER_CREATED", actor_type="USER", actor_id=user.id,
        safe_payload={"display_name": customer.display_name},
    )
    return _serialize(customer)


@router.patch("/{customer_id}")
def update_customer(
    customer_id: str,
    payload: CustomerRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR", "INVOICE_APPROVER"))],
) -> dict:
    customer = db.query(Customer).filter_by(id=customer_id).one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")

    customer.display_name = payload.display_name
    customer.legal_name = payload.legal_name
    customer.email = payload.email.strip().lower() if payload.email else None
    customer.phone = payload.phone
    customer.gstin = payload.gstin
    customer.billing_address_json = payload.billing_address
    customer.shipping_address_json = payload.shipping_address
    customer.state_name = payload.state_name
    customer.state_code = payload.state_code
    customer.preferred_delivery_channels_json = payload.preferred_delivery_channels
    customer.verification_status = "REVIEWED"
    db.add(customer)
    db.commit()
    record_event(
        db, correlation_id=customer.id, entity_type="Customer", entity_id=customer.id,
        event_name="CUSTOMER_UPDATED", actor_type="USER", actor_id=user.id,
        safe_payload={"display_name": customer.display_name},
    )
    return _serialize(customer)
