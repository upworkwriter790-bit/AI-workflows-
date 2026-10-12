"""Idempotency reservation for inbound webhooks and outbound mutating
calls (ERP posting, email send, Operations notification — Phase 3 reuses
this same primitive). Backed by `IdempotencyRecord`'s unique
`(operation_name, idempotency_key)` constraint so a race between two
concurrent deliveries of the same event can only ever let one through.
"""

from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyRecord


class ReservationStatus(str, enum.Enum):
    RESERVED = "RESERVED"  # first time seeing this key — caller should proceed
    DUPLICATE = "DUPLICATE"  # already processing or completed — caller must not re-process


@dataclass
class ReservationResult:
    status: ReservationStatus
    record: IdempotencyRecord | None = None


def hash_request_body(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def reserve(db: Session, *, operation_name: str, idempotency_key: str, request_hash: str) -> ReservationResult:
    """Atomically reserve `(operation_name, idempotency_key)`.

    Per spec §8: a repeated delivery of an event already processing or
    completed must be rejected (409), never silently re-run. We rely on the
    DB's unique constraint rather than a check-then-insert race.
    """
    record = IdempotencyRecord(
        operation_name=operation_name,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        status="PROCESSING",
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(IdempotencyRecord)
            .filter_by(operation_name=operation_name, idempotency_key=idempotency_key)
            .one()
        )
        return ReservationResult(status=ReservationStatus.DUPLICATE, record=existing)

    db.refresh(record)
    return ReservationResult(status=ReservationStatus.RESERVED, record=record)


def mark_completed(db: Session, record: IdempotencyRecord, *, response_reference: str | None = None) -> None:
    record.status = "COMPLETED"
    record.response_reference = response_reference
    db.add(record)
    db.commit()


def mark_failed(db: Session, record: IdempotencyRecord) -> None:
    record.status = "FAILED"
    db.add(record)
    db.commit()
