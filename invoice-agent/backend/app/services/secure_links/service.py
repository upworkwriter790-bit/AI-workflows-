"""Secure invoice-download links (spec §11). The opaque token is handed to
the caller exactly once, at creation time — only its SHA-256 hash is ever
persisted, so a leaked database never leaks a usable token. Validation
checks expiry, revocation, and remaining download count before allowing
each access.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.secure_download_link import SecureDownloadLink

TOKEN_BYTES = 32


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class CreatedLink:
    token: str  # only ever returned once, by this function
    record: SecureDownloadLink


def create_link(
    db: Session,
    *,
    document_id: str,
    delivery_id: str,
    expiry_days: int,
    max_downloads: int,
) -> CreatedLink:
    token = secrets.token_urlsafe(TOKEN_BYTES)
    record = SecureDownloadLink(
        document_id=document_id,
        delivery_id=delivery_id,
        token_hash=_hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=expiry_days),
        max_downloads=max_downloads,
        download_count=0,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return CreatedLink(token=token, record=record)


class LinkAccessDenied(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def resolve_and_consume(db: Session, token: str) -> SecureDownloadLink:
    """Validates the token and, if valid, increments download_count.
    Raises LinkAccessDenied with a reason ('not_found', 'revoked',
    'expired', 'download_limit_reached') otherwise.
    """
    record = db.query(SecureDownloadLink).filter_by(token_hash=_hash_token(token)).one_or_none()
    if record is None:
        raise LinkAccessDenied("not_found")
    if record.revoked_at is not None:
        raise LinkAccessDenied("revoked")

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise LinkAccessDenied("expired")

    if record.download_count >= record.max_downloads:
        raise LinkAccessDenied("download_limit_reached")

    record.download_count += 1
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def revoke_link(db: Session, record: SecureDownloadLink) -> None:
    record.revoked_at = datetime.now(timezone.utc)
    db.add(record)
    db.commit()
