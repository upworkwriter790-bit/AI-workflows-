"""Celery task wrapper around the order workflow. Retries with exponential
backoff on unexpected exceptions (network blips, transient DB errors) —
the workflow itself is idempotent-safe to re-run because every status
transition is driven by the Invoice row's own current state, and a
second run against an already-`INVOICE_PDF_GENERATED` order is a no-op
once Phase 3 adds a guard for "already past this stage" (tracked as
follow-up; Phase 2 does not yet re-enter a completed invoice).
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.tasks.celery_app import celery_app
from app.workflows.order_workflow import process_paid_order

logger = get_logger(__name__)


@celery_app.task(
    name="process_paid_order",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 5},
)
def process_paid_order_task(self, order_id: str) -> str:
    settings = get_settings()
    db = SessionLocal()
    try:
        outcome = process_paid_order(db, order_id, settings)
        logger.info(
            "order_workflow_finished",
            order_id=order_id,
            invoice_id=outcome.invoice.id,
            invoice_status=outcome.invoice.invoice_status,
        )
        return outcome.invoice.invoice_status
    finally:
        db.close()
