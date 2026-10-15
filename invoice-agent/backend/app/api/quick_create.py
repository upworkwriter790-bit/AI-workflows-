"""Mode B1 — Quick Create API. /resolve never writes anything; /draft
re-resolves server-side (never trusts a client-sent "ready" flag) and
only then calls into the normal draft-creation workflow — from that
point on a quick-created draft is indistinguishable from a detailed-form
one: same PENDING_HUMAN_REVIEW state, same edit/AI-proposal/approve
endpoints.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import InternalUser, require_role
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.quick_create import QuickCreateInput
from app.workflows.generated_invoice_workflow import (
    GeneratedInvoiceValidationError,
    TotalMismatchError,
    create_draft_generated_invoice,
)
from app.workflows.quick_create_workflow import (
    build_request_from_resolution,
    resolve_quick_create,
)

router = APIRouter(prefix="/api/v1/quick-create", tags=["quick-create"])


def _resolution_response(resolution) -> dict:
    return {
        "outcome": resolution.outcome,
        "customer": resolution.customer,
        "product": resolution.product,
        "missing_critical_fields": resolution.missing_critical_fields,
        "clarification": resolution.clarification,
        "warnings": resolution.warnings,
        "reviewer_summary": resolution.reviewer_summary,
    }


@router.post("/resolve")
def resolve(
    payload: QuickCreateInput,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR"))],
) -> dict:
    resolution = resolve_quick_create(db, settings, payload)
    return _resolution_response(resolution)


@router.post("/draft", status_code=201)
def create_draft(
    payload: QuickCreateInput,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[InternalUser, Depends(require_role("ADMIN", "INVOICE_EDITOR"))],
) -> dict:
    resolution = resolve_quick_create(db, settings, payload)
    if resolution.outcome != "READY_FOR_DRAFT":
        raise HTTPException(status_code=409, detail=_resolution_response(resolution))

    request = build_request_from_resolution(settings, payload, resolution)
    try:
        outcome = create_draft_generated_invoice(db, settings, request, created_by_user_id=user.id)
    except GeneratedInvoiceValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    except TotalMismatchError as exc:
        raise HTTPException(status_code=422, detail={"total_mismatch": exc.mismatches}) from exc

    gi = outcome.generated_invoice
    return {
        "invoice_id": gi.id,
        "status": gi.status,
        "grand_total": float(gi.grand_total) if gi.grand_total is not None else None,
        "resolution": _resolution_response(resolution),
    }
