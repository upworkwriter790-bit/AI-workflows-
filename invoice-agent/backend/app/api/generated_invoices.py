"""Method B intake — spec §4: payment/order details in, a generated
invoice PDF queued for delivery out.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import InternalUser, require_role
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.delivery_attempt import DeliveryAttempt
from app.schemas.generated_invoice_request import GeneratedInvoiceDeliveryRequest
from app.workflows.generated_invoice_workflow import (
    GeneratedInvoiceValidationError,
    TotalMismatchError,
    process_generated_invoice_request,
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


@router.post("", status_code=202)
def create_generated_invoice_delivery(
    request: GeneratedInvoiceDeliveryRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER"))],
) -> dict:
    try:
        outcome = process_generated_invoice_request(db, settings, request, created_by_user_id=user.id)
    except GeneratedInvoiceValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    except TotalMismatchError as exc:
        raise HTTPException(status_code=422, detail={"total_mismatch": exc.mismatches}) from exc

    gi = outcome.generated_invoice
    if gi.status in _FAILURE_STATUSES:
        raise HTTPException(
            status_code=422,
            detail={"status": gi.status, "message": "this idempotency_key previously failed; submit a new key with corrected data"},
        )

    requested_channels: list[str] = []
    if outcome.delivery_id:
        attempts = db.query(DeliveryAttempt).filter_by(delivery_id=outcome.delivery_id).all()
        requested_channels = sorted({a.channel.lower() for a in attempts})

        if not outcome.is_duplicate_replay:
            from app.tasks.delivery_tasks import send_email_attempt_task, send_whatsapp_attempt_task

            for attempt in attempts:
                if attempt.channel == "EMAIL":
                    send_email_attempt_task.delay(
                        attempt.id,
                        attach_pdf=request.delivery.attach_pdf_to_email,
                        include_download_link=request.delivery.include_secure_download_link,
                    )
                elif attempt.channel == "WHATSAPP" and request.delivery.send_whatsapp_notification:
                    send_whatsapp_attempt_task.delay(
                        attempt.id, include_download_link=request.delivery.include_secure_download_link
                    )

    return {
        "delivery_id": outcome.delivery_id,
        "document_id": outcome.invoice_document.id if outcome.invoice_document else None,
        "invoice_id": gi.id,
        "invoice_number": gi.invoice_number,
        "correlation_id": gi.correlation_id,
        "status": gi.status,
        "requested_channels": requested_channels,
        "created_at": gi.created_at.isoformat() if gi.created_at else None,
    }
