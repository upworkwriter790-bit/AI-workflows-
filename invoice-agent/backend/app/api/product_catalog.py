"""Product/tax catalog (spec: "you must also provide a product/tax
catalog before production"). Prevents a Method-B caller from inventing
HSN/SAC codes and GST rates per invoice — see
app/workflows/generated_invoice_workflow.py's catalog cross-check.
Create/update is ADMIN-only; every change is an audit event.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.auth import InternalUser, require_role
from app.db.session import get_db
from app.models.product_catalog_item import ProductCatalogItem
from app.services.audit.service import record_event

router = APIRouter(prefix="/api/v1/product-catalog", tags=["product-catalog"])


class ProductCatalogItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    internal_reference: str = Field(min_length=1, max_length=64)
    display_description: str
    product_type: str = Field(pattern="^(GOODS|SERVICE)$")
    hsn_or_sac_code: str
    unit: str
    unit_price: float
    gst_rate: float
    tax_category: str | None = None
    active: bool = True
    aliases: list[str] = Field(default_factory=list)


def _serialize(item: ProductCatalogItem) -> dict:
    return {
        "id": item.id,
        "internal_reference": item.internal_reference,
        "display_description": item.display_description,
        "product_type": item.product_type,
        "hsn_or_sac_code": item.hsn_or_sac_code,
        "unit": item.unit,
        "unit_price": float(item.unit_price),
        "gst_rate": float(item.gst_rate),
        "tax_category": item.tax_category,
        "active": item.active,
        "aliases": item.aliases_json or [],
    }


@router.get("")
def list_product_catalog(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER", "DELIVERY_VIEWER"))],
    active_only: bool = True,
) -> dict:
    query = db.query(ProductCatalogItem)
    if active_only:
        query = query.filter_by(active=True)
    return {"items": [_serialize(i) for i in query.order_by(ProductCatalogItem.internal_reference).all()]}


@router.post("", status_code=201)
def create_product_catalog_item(
    payload: ProductCatalogItemRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN"))],
) -> dict:
    existing = db.query(ProductCatalogItem).filter_by(internal_reference=payload.internal_reference).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="internal_reference already exists")

    data = payload.model_dump()
    data["aliases_json"] = data.pop("aliases")
    item = ProductCatalogItem(**data)
    db.add(item)
    db.commit()
    record_event(
        db, correlation_id=item.id, entity_type="ProductCatalogItem", entity_id=item.id,
        event_name="CATALOG_ITEM_CREATED", actor_type="USER", actor_id=user.id,
        safe_payload={"internal_reference": item.internal_reference},
    )
    return _serialize(item)


@router.patch("/{item_id}")
def update_product_catalog_item(
    item_id: str,
    payload: ProductCatalogItemRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN"))],
) -> dict:
    item = db.query(ProductCatalogItem).filter_by(id=item_id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="catalog item not found")

    data = payload.model_dump()
    data["aliases_json"] = data.pop("aliases")
    for field, value in data.items():
        setattr(item, field, value)
    db.add(item)
    db.commit()
    record_event(
        db, correlation_id=item.id, entity_type="ProductCatalogItem", entity_id=item.id,
        event_name="CATALOG_ITEM_UPDATED", actor_type="USER", actor_id=user.id,
        safe_payload={"internal_reference": item.internal_reference, "active": item.active},
    )
    return _serialize(item)
