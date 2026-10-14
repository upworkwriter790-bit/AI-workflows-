"""Method B — spec §4 plus the human draft/approve gate added on top:
payment/order details in, a DRAFT generated invoice out for review/
editing, and only on explicit approval does it get a real invoice
number, a rendered PDF, and a queued delivery.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import InternalUser, require_role
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.generated_invoice import GeneratedInvoice
from app.models.generated_invoice_line_item import GeneratedInvoiceLineItem
from app.schemas.generated_invoice_request import GeneratedInvoiceDeliveryRequest
from app.services.audit.service import record_event
from app.workflows.generated_invoice_workflow import (
    GeneratedInvoiceNotDraftError,
    GeneratedInvoiceOutcome,
    GeneratedInvoiceValidationError,
    TotalMismatchError,
    approve_and_finalize,
    create_draft_generated_invoice,
    edit_draft_generated_invoice,
)

router = APIRouter(prefix="/api/v1/generated-invoice-deliveries", tags=["generated-invoice-deliveries"])

_FAILURE_STATUSES = {
    "INVALID_REQUEST",
    "CALCULATION_FAILED",
    "TOTAL_MISMATCH",
    "INVOICE_NUMBER_RESERVATION_FAILED",
    "PDF_RENDER_FAILED",
    "STORAGE_FAILED",
}


def _response(outcome: GeneratedInvoiceOutcome) -> dict:
    gi = outcome.generated_invoice
    return {
        "delivery_id": outcome.delivery_id,
        "document_id": outcome.invoice_document.id if outcome.invoice_document else None,
        "invoice_id": gi.id,
        "invoice_number": gi.invoice_number,
        "correlation_id": gi.correlation_id,
        "status": gi.status,
        "requested_channels": gi.requested_channels_json,
        "grand_total": float(gi.grand_total) if gi.grand_total is not None else None,
        "created_at": gi.created_at.isoformat() if gi.created_at else None,
    }


def _line_items_response(db: Session, generated_invoice_id: str) -> list[dict]:
    items = (
        db.query(GeneratedInvoiceLineItem)
        .filter_by(generated_invoice_id=generated_invoice_id)
        .order_by(GeneratedInvoiceLineItem.line_number)
        .all()
    )
    return [
        {
            "line_number": li.line_number,
            "item_reference": li.item_reference,
            "description": li.description,
            "hsn_or_sac_code": li.hsn_or_sac_code,
            "quantity": float(li.quantity),
            "unit": li.unit,
            "unit_price": float(li.unit_price),
            "discount_amount": float(li.discount_amount),
            "taxable_value": float(li.taxable_value),
            "gst_rate": float(li.gst_rate),
            "cgst_amount": float(li.cgst_amount),
            "sgst_amount": float(li.sgst_amount),
            "igst_amount": float(li.igst_amount),
            "line_total": float(li.line_total),
        }
        for li in items
    ]


@router.post("", status_code=201)
def create_generated_invoice_draft(
    request: GeneratedInvoiceDeliveryRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER"))],
) -> dict:
    try:
        outcome = create_draft_generated_invoice(db, settings, request, created_by_user_id=user.id)
    except GeneratedInvoiceValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    except TotalMismatchError as exc:
        raise HTTPException(status_code=422, detail={"total_mismatch": exc.mismatches}) from exc

    if outcome.generated_invoice.status in _FAILURE_STATUSES:
        raise HTTPException(
            status_code=422,
            detail={
                "status": outcome.generated_invoice.status,
                "message": "this idempotency_key previously failed; submit a new key with corrected data",
            },
        )
    return _response(outcome)


@router.get("")
def list_generated_invoices(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER", "DELIVERY_VIEWER"))],
    status_filter: str | None = None,
) -> dict:
    query = db.query(GeneratedInvoice)
    if status_filter:
        query = query.filter(GeneratedInvoice.status == status_filter)
    results = []
    for gi in query.order_by(GeneratedInvoice.created_at.desc()).all():
        results.append(
            {
                "invoice_id": gi.id,
                "external_reference": gi.external_reference,
                "payment_reference": gi.payment_reference,
                "invoice_number": gi.invoice_number,
                "recipient_name": gi.recipient_name,
                "grand_total": float(gi.grand_total) if gi.grand_total is not None else None,
                "status": gi.status,
                "created_at": gi.created_at.isoformat() if gi.created_at else None,
            }
        )
    return {"generated_invoices": results, "count": len(results)}


@router.get("/{invoice_id}")
def get_generated_invoice(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER", "DELIVERY_VIEWER"))],
) -> dict:
    gi = db.query(GeneratedInvoice).filter_by(id=invoice_id).one_or_none()
    if gi is None:
        raise HTTPException(status_code=404, detail="generated invoice not found")

    return {
        "invoice_id": gi.id,
        "status": gi.status,
        "is_editable": gi.status == "DRAFT",
        "external_reference": gi.external_reference,
        "payment_reference": gi.payment_reference,
        "payment_date": gi.payment_date.isoformat() if gi.payment_date else None,
        "invoice_number": gi.invoice_number,
        "invoice_date": gi.invoice_date.isoformat() if gi.invoice_date else None,
        "currency": gi.currency,
        "tax_inclusive": gi.tax_inclusive,
        "recipient_name": gi.recipient_name,
        "recipient_email": gi.recipient_email,
        "recipient_phone": gi.recipient_phone,
        "recipient_gstin": gi.recipient_gstin,
        "billing_address": gi.billing_address_json,
        "shipping_address": gi.shipping_address_json,
        "place_of_supply": gi.place_of_supply,
        "subtotal": float(gi.subtotal),
        "discount_total": float(gi.discount_total),
        "taxable_total": float(gi.taxable_total),
        "cgst_total": float(gi.cgst_total),
        "sgst_total": float(gi.sgst_total),
        "igst_total": float(gi.igst_total),
        "cess_total": float(gi.cess_total),
        "tax_total": float(gi.tax_total),
        "grand_total": float(gi.grand_total),
        "amount_in_words": gi.amount_in_words,
        "line_items": _line_items_response(db, gi.id),
        "requested_channels": gi.requested_channels_json,
        "document_id": gi.invoice_document_id,
        "approved_by_user_id": gi.approved_by_user_id,
        "approved_at": gi.approved_at.isoformat() if gi.approved_at else None,
        "created_at": gi.created_at.isoformat() if gi.created_at else None,
    }


@router.patch("/{invoice_id}")
def edit_generated_invoice_draft(
    invoice_id: str,
    request: GeneratedInvoiceDeliveryRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER"))],
) -> dict:
    """Full replacement of the draft's content (recipient, payment/order
    details, line items, delivery options) while status is DRAFT. Not
    available once the invoice has been approved — it is immutable from
    that point on.
    """
    gi = db.query(GeneratedInvoice).filter_by(id=invoice_id).one_or_none()
    if gi is None:
        raise HTTPException(status_code=404, detail="generated invoice not found")

    try:
        edit_draft_generated_invoice(db, settings, gi, request, edited_by_user_id=user.id)
    except GeneratedInvoiceNotDraftError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GeneratedInvoiceValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    except TotalMismatchError as exc:
        raise HTTPException(status_code=422, detail={"total_mismatch": exc.mismatches}) from exc

    return _response(GeneratedInvoiceOutcome(generated_invoice=gi, invoice_document=None, delivery_id=None))


@router.post("/{invoice_id}/approve")
def approve_generated_invoice(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER"))],
) -> dict:
    """Finalizes the draft (reserves the invoice number, renders and
    stores the PDF) and immediately queues it for delivery. Irreversible
    — the invoice is immutable after this call.
    """
    gi = db.query(GeneratedInvoice).filter_by(id=invoice_id).one_or_none()
    if gi is None:
        raise HTTPException(status_code=404, detail="generated invoice not found")

    try:
        outcome = approve_and_finalize(db, settings, gi, approved_by_user_id=user.id)
    except GeneratedInvoiceNotDraftError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    from app.models.delivery_attempt import DeliveryAttempt
    from app.tasks.delivery_tasks import (
        send_email_attempt_task,
        send_whatsapp_attempt_task,
    )

    for attempt in db.query(DeliveryAttempt).filter_by(delivery_id=outcome.delivery_id).all():
        if attempt.channel == "EMAIL":
            send_email_attempt_task.delay(
                attempt.id, attach_pdf=gi.attach_pdf_to_email, include_download_link=gi.include_download_link
            )
        elif attempt.channel == "WHATSAPP" and gi.send_whatsapp_notification:
            send_whatsapp_attempt_task.delay(attempt.id, include_download_link=gi.include_download_link)

    return _response(outcome)


@router.post("/{invoice_id}/discard")
def discard_generated_invoice_draft(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER"))],
) -> dict:
    """Abandons a DRAFT before approval. No invoice number was ever
    reserved for a draft, so discarding one leaves no gap in the
    invoice-number sequence.
    """
    gi = db.query(GeneratedInvoice).filter_by(id=invoice_id).one_or_none()
    if gi is None:
        raise HTTPException(status_code=404, detail="generated invoice not found")
    if gi.status != "DRAFT":
        raise HTTPException(status_code=409, detail=f"cannot discard a generated invoice in status {gi.status}")

    gi.status = "CANCELLED"
    db.add(gi)
    db.commit()
    record_event(
        db, correlation_id=gi.correlation_id, entity_type="GeneratedInvoice", entity_id=gi.id,
        event_name="DRAFT_DISCARDED", actor_type="USER", actor_id=user.id,
        previous_state="DRAFT", new_state="CANCELLED",
    )
    return {"invoice_id": gi.id, "status": "CANCELLED"}
