"""Append-only audit trail. Every workflow transition in both use cases
writes exactly one AuditEvent here — never update, never delete.

`safe_payload` must already be redaction-safe before it reaches this
function (callers should keep it to IDs, status strings, and non-sensitive
summaries — not raw GSTINs, full addresses, or document bytes).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent


def record_event(
    db: Session,
    *,
    correlation_id: str,
    entity_type: str,
    entity_id: str,
    event_name: str,
    actor_type: str,
    actor_id: str | None = None,
    previous_state: str | None = None,
    new_state: str | None = None,
    safe_payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        correlation_id=correlation_id,
        entity_type=entity_type,
        entity_id=entity_id,
        event_name=event_name,
        previous_state=previous_state,
        new_state=new_state,
        actor_type=actor_type,
        actor_id=actor_id,
        safe_payload_json=safe_payload or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_audit_trail(db: Session, *, entity_type: str, entity_id: str) -> list[AuditEvent]:
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
        .order_by(AuditEvent.created_at.asc())
        .all()
    )
