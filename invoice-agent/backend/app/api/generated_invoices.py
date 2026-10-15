"""Method B — payment/order details in, a versioned draft held for
human review, edited manually or via an AI-generated (never
AI-applied) proposal, and only sent after an authorized approval.

Route prefix stays `/api/v1/generated-invoice-deliveries` (the name this
resource already had in this codebase) rather than introducing a second,
inconsistent `/api/v1/generated-invoices` prefix for the same resource —
every path below is otherwise exactly what was asked for (drafts list,
versions, ai-edit-proposals, approve/reject/cancel).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.auth import InternalUser, require_role
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.generated_invoice import GeneratedInvoice
from app.models.generated_invoice_line_item import GeneratedInvoiceLineItem
from app.models.invoice_draft_version import InvoiceDraftVersion
from app.models.invoice_edit_proposal import InvoiceEditProposal
from app.schemas.generated_invoice_request import GeneratedInvoiceDeliveryRequest
from app.services.audit.service import get_audit_trail
from app.workflows.generated_invoice_workflow import (
    PENDING_REVIEW,
    AIEditUnavailableError,
    GeneratedInvoiceOutcome,
    GeneratedInvoiceValidationError,
    InvalidInvoiceStateError,
    ProposalNotApplicableError,
    StaleProposalError,
    TotalMismatchError,
    apply_ai_edit_proposal,
    approve_and_finalize,
    cancel_generated_invoice,
    create_draft_generated_invoice,
    edit_draft_generated_invoice,
    generate_ai_edit_proposal,
    reject_ai_edit_proposal,
    reject_generated_invoice,
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


class RejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


class AIEditProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str


def _response(outcome: GeneratedInvoiceOutcome) -> dict:
    gi = outcome.generated_invoice
    return {
        "delivery_id": outcome.delivery_id,
        "document_id": outcome.invoice_document.id if outcome.invoice_document else None,
        "invoice_id": gi.id,
        "invoice_number": gi.invoice_number,
        "correlation_id": gi.correlation_id,
        "status": gi.status,
        "current_version_number": gi.current_version_number,
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


def _get_or_404(db: Session, invoice_id: str) -> GeneratedInvoice:
    gi = db.query(GeneratedInvoice).filter_by(id=invoice_id).one_or_none()
    if gi is None:
        raise HTTPException(status_code=404, detail="generated invoice not found")
    return gi


@router.post("", status_code=201)
def create_generated_invoice_draft(
    request: GeneratedInvoiceDeliveryRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR"))],
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
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER", "DELIVERY_VIEWER", "INVOICE_EDITOR", "INVOICE_APPROVER"))],
    status_filter: str | None = None,
) -> dict:
    query = db.query(GeneratedInvoice)
    if status_filter:
        query = query.filter(GeneratedInvoice.status == status_filter)
    results = [_summary(gi) for gi in query.order_by(GeneratedInvoice.created_at.desc()).all()]
    return {"generated_invoices": results, "count": len(results)}


@router.get("/drafts")
def list_drafts(
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR", "INVOICE_APPROVER"))],
) -> dict:
    """The human-review dashboard's draft list — every invoice currently
    sitting in PENDING_HUMAN_REVIEW.
    """
    query = db.query(GeneratedInvoice).filter_by(status=PENDING_REVIEW)
    results = [_summary(gi) for gi in query.order_by(GeneratedInvoice.created_at.desc()).all()]
    return {"drafts": results, "count": len(results)}


def _summary(gi: GeneratedInvoice) -> dict:
    return {
        "invoice_id": gi.id,
        "external_reference": gi.external_reference,
        "payment_reference": gi.payment_reference,
        "invoice_number": gi.invoice_number,
        "recipient_name": gi.recipient_name,
        "grand_total": float(gi.grand_total) if gi.grand_total is not None else None,
        "status": gi.status,
        "current_version_number": gi.current_version_number,
        "created_by_user_id": gi.created_by_user_id,
        "created_at": gi.created_at.isoformat() if gi.created_at else None,
    }


@router.get("/{invoice_id}")
def get_generated_invoice(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "DELIVERY_MANAGER", "DELIVERY_VIEWER", "INVOICE_EDITOR", "INVOICE_APPROVER"))],
) -> dict:
    gi = _get_or_404(db, invoice_id)
    timeline = get_audit_trail(db, entity_type="GeneratedInvoice", entity_id=gi.id)

    return {
        "invoice_id": gi.id,
        "status": gi.status,
        "is_editable": gi.status == PENDING_REVIEW,
        "is_approvable": gi.status == PENDING_REVIEW,
        "current_version_number": gi.current_version_number,
        "approved_version_number": gi.approved_version_number,
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
        "final_document_id": gi.final_document_id,
        "approved_by_user_id": gi.approved_by_user_id,
        "approved_at": gi.approved_at.isoformat() if gi.approved_at else None,
        "rejected_by_user_id": gi.rejected_by_user_id,
        "rejected_at": gi.rejected_at.isoformat() if gi.rejected_at else None,
        "rejection_reason": gi.rejection_reason,
        "created_at": gi.created_at.isoformat() if gi.created_at else None,
        "audit_timeline": [
            {
                "event_name": e.event_name, "actor_type": e.actor_type, "actor_id": e.actor_id,
                "previous_state": e.previous_state, "new_state": e.new_state,
                "safe_payload": e.safe_payload_json, "created_at": e.created_at.isoformat(),
            }
            for e in timeline
        ],
    }


@router.get("/{invoice_id}/versions")
def list_versions(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR", "INVOICE_APPROVER", "DELIVERY_VIEWER"))],
) -> dict:
    _get_or_404(db, invoice_id)
    versions = (
        db.query(InvoiceDraftVersion)
        .filter_by(generated_invoice_id=invoice_id)
        .order_by(InvoiceDraftVersion.version_number)
        .all()
    )
    return {
        "versions": [
            {
                "version_number": v.version_number,
                "parent_version_number": v.parent_version_number,
                "created_by_type": v.created_by_type,
                "created_by_user_id": v.created_by_user_id,
                "creation_reason": v.creation_reason,
                "change_summary": v.change_summary,
                "is_current": v.is_current,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ]
    }


@router.get("/{invoice_id}/versions/{version_number}")
def get_version(
    invoice_id: str,
    version_number: int,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR", "INVOICE_APPROVER", "DELIVERY_VIEWER"))],
) -> dict:
    _get_or_404(db, invoice_id)
    version = (
        db.query(InvoiceDraftVersion)
        .filter_by(generated_invoice_id=invoice_id, version_number=version_number)
        .one_or_none()
    )
    if version is None:
        raise HTTPException(status_code=404, detail="version not found")
    return {
        "version_number": version.version_number,
        "parent_version_number": version.parent_version_number,
        "created_by_type": version.created_by_type,
        "created_by_user_id": version.created_by_user_id,
        "creation_reason": version.creation_reason,
        "invoice_data_snapshot": version.invoice_data_snapshot_json,
        "line_items_snapshot": version.line_items_snapshot_json,
        "calculation_snapshot": version.calculation_snapshot_json,
        "change_summary": version.change_summary,
        "draft_pdf_available": version.draft_pdf_storage_key is not None,
        "created_at": version.created_at.isoformat(),
    }


@router.get("/{invoice_id}/versions/{version_number}/pdf")
def download_version_pdf(
    invoice_id: str,
    version_number: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR", "INVOICE_APPROVER", "DELIVERY_VIEWER"))],
):
    from fastapi import Response

    from app.services.storage.factory import get_storage_adapter

    _get_or_404(db, invoice_id)
    version = (
        db.query(InvoiceDraftVersion)
        .filter_by(generated_invoice_id=invoice_id, version_number=version_number)
        .one_or_none()
    )
    if version is None or version.draft_pdf_storage_key is None:
        raise HTTPException(status_code=404, detail="draft PDF not available for this version")
    storage = get_storage_adapter(settings)
    pdf_bytes = storage.read(version.draft_pdf_storage_key)
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.patch("/{invoice_id}")
def edit_generated_invoice_draft(
    invoice_id: str,
    request: GeneratedInvoiceDeliveryRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR"))],
) -> dict:
    """Full-replace manual edit of the draft's content while it is
    PENDING_HUMAN_REVIEW. Recalculates and creates a new, immutable
    draft version — never mutates the previous one.
    """
    gi = _get_or_404(db, invoice_id)
    try:
        edit_draft_generated_invoice(db, settings, gi, request, edited_by_user_id=user.id)
    except InvalidInvoiceStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GeneratedInvoiceValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    except TotalMismatchError as exc:
        raise HTTPException(status_code=422, detail={"total_mismatch": exc.mismatches}) from exc

    return _response(GeneratedInvoiceOutcome(generated_invoice=gi, invoice_document=None, delivery_id=None))


@router.post("/{invoice_id}/ai-edit-proposals", status_code=201)
def create_ai_edit_proposal(
    invoice_id: str,
    body: AIEditProposalRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR"))],
) -> dict:
    """Generates a proposal only — never applies it. The AI has no path
    to the database here beyond this one row.
    """
    gi = _get_or_404(db, invoice_id)
    try:
        proposal = generate_ai_edit_proposal(db, settings, gi, body.instruction, requested_by_user_id=user.id)
    except InvalidInvoiceStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AIEditUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _proposal_response(proposal)


def _proposal_response(proposal: InvoiceEditProposal) -> dict:
    return {
        "proposal_id": proposal.id,
        "generated_invoice_id": proposal.generated_invoice_id,
        "base_draft_version_number": proposal.base_draft_version_number,
        "status": proposal.status,
        "instruction": proposal.natural_language_instruction,
        "proposed_change_summary": proposal.proposed_change_summary,
        "structured_change_proposal": proposal.structured_change_proposal_json,
        "validation_result": proposal.validation_result_json,
        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
    }


def _get_proposal_or_404(db: Session, invoice_id: str, proposal_id: str) -> InvoiceEditProposal:
    proposal = (
        db.query(InvoiceEditProposal)
        .filter_by(id=proposal_id, generated_invoice_id=invoice_id)
        .one_or_none()
    )
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    return proposal


@router.get("/{invoice_id}/ai-edit-proposals/{proposal_id}")
def get_ai_edit_proposal(
    invoice_id: str,
    proposal_id: str,
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR", "INVOICE_APPROVER"))],
) -> dict:
    _get_or_404(db, invoice_id)
    return _proposal_response(_get_proposal_or_404(db, invoice_id, proposal_id))


@router.post("/{invoice_id}/ai-edit-proposals/{proposal_id}/apply")
def apply_ai_edit_proposal_endpoint(
    invoice_id: str,
    proposal_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR"))],
) -> dict:
    """A human explicitly applying a proposal — this is the ONLY way a
    proposal's content ever reaches the draft. Never automatic.
    """
    gi = _get_or_404(db, invoice_id)
    proposal = _get_proposal_or_404(db, invoice_id, proposal_id)
    try:
        apply_ai_edit_proposal(db, settings, gi, proposal, applied_by_user_id=user.id)
    except InvalidInvoiceStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ProposalNotApplicableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except StaleProposalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GeneratedInvoiceValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc

    return _response(GeneratedInvoiceOutcome(generated_invoice=gi, invoice_document=None, delivery_id=None))


@router.post("/{invoice_id}/ai-edit-proposals/{proposal_id}/reject")
def reject_ai_edit_proposal_endpoint(
    invoice_id: str,
    proposal_id: str,
    body: CancelRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR"))],
) -> dict:
    gi = _get_or_404(db, invoice_id)
    proposal = _get_proposal_or_404(db, invoice_id, proposal_id)
    reject_ai_edit_proposal(db, gi, proposal, rejected_by_user_id=user.id, reason=body.reason)
    return _proposal_response(proposal)


@router.post("/{invoice_id}/approve")
def approve_generated_invoice(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_APPROVER"))],
) -> dict:
    """The ONLY path to delivery. Locks the approved version, renders
    the final (unwatermarked) PDF, and queues email/WhatsApp — always a
    human action, never AI, never automatic.
    """
    gi = _get_or_404(db, invoice_id)
    try:
        outcome = approve_and_finalize(db, settings, gi, approved_by_user_id=user.id)
    except InvalidInvoiceStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GeneratedInvoiceValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc

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


@router.post("/{invoice_id}/reject")
def reject_generated_invoice_endpoint(
    invoice_id: str,
    body: RejectRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_APPROVER"))],
) -> dict:
    gi = _get_or_404(db, invoice_id)
    try:
        reject_generated_invoice(db, gi, rejected_by_user_id=user.id, reason=body.reason)
    except InvalidInvoiceStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"invoice_id": gi.id, "status": gi.status}


@router.post("/{invoice_id}/cancel")
def cancel_generated_invoice_endpoint(
    invoice_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR", "INVOICE_APPROVER"))],
    body: CancelRequest = CancelRequest(),
) -> dict:
    gi = _get_or_404(db, invoice_id)
    try:
        cancel_generated_invoice(db, gi, cancelled_by_user_id=user.id, reason=body.reason)
    except InvalidInvoiceStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"invoice_id": gi.id, "status": gi.status}
