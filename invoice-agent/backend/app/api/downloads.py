"""Public secure-download route (spec §11, §14: GET /d/{opaque_download_token}).
No auth — the opaque token itself is the credential. Never exposes the
underlying storage key or a permanent object URL; streams the file (or,
for a real cloud storage adapter, redirects to a short-lived signed URL).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.invoice_document import InvoiceDocument
from app.services.audit.service import record_event
from app.services.secure_links.service import LinkAccessDenied, resolve_and_consume
from app.services.storage.factory import get_storage_adapter

router = APIRouter(tags=["downloads"])


@router.get("/d/{token}")
def download_invoice(
    token: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        link = resolve_and_consume(db, token)
    except LinkAccessDenied as exc:
        raise HTTPException(status_code=404, detail="link is invalid, expired, or no longer available") from exc

    document = db.query(InvoiceDocument).filter_by(id=link.document_id).one()

    record_event(
        db,
        correlation_id=link.delivery_id,
        entity_type="SecureDownloadLink",
        entity_id=link.id,
        event_name="SECURE_LINK_ACCESSED",
        actor_type="API",
        safe_payload={"download_count": link.download_count, "max_downloads": link.max_downloads},
    )

    storage = get_storage_adapter(settings)
    if storage.supports_direct_streaming:
        data = storage.read(document.storage_key)
        return Response(content=data, media_type="application/pdf")

    signed_url = storage.get_signed_url(document.storage_key, expires_in_seconds=300)
    return RedirectResponse(url=signed_url)
