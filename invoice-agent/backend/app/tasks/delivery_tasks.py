"""Celery tasks wrapping per-channel dispatch. Retry scheduling follows
the workflow's own `DispatchOutcome` (spec §12's fixed 1m/5m/30m/2h
schedule, max 4 attempts) rather than Celery's generic backoff — the
workflow already decided whether/when to retry, Celery just executes
the sleep.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.delivery_attempt import DeliveryAttempt
from app.tasks.celery_app import celery_app
from app.workflows.delivery_workflow import dispatch_email_attempt, dispatch_whatsapp_attempt


@celery_app.task(name="send_email_attempt", bind=True)
def send_email_attempt_task(self, attempt_id: str, *, attach_pdf: bool, include_download_link: bool) -> str:
    settings = get_settings()
    db = SessionLocal()
    try:
        attempt = db.query(DeliveryAttempt).filter_by(id=attempt_id).one()
        outcome = dispatch_email_attempt(
            db, settings, attempt, attach_pdf=attach_pdf, include_download_link=include_download_link
        )
        if outcome.should_retry:
            raise self.retry(countdown=outcome.retry_after_seconds)
        return attempt.status
    finally:
        db.close()


@celery_app.task(name="send_whatsapp_attempt", bind=True)
def send_whatsapp_attempt_task(self, attempt_id: str, *, include_download_link: bool) -> str:
    settings = get_settings()
    db = SessionLocal()
    try:
        attempt = db.query(DeliveryAttempt).filter_by(id=attempt_id).one()
        outcome = dispatch_whatsapp_attempt(db, settings, attempt, include_download_link=include_download_link)
        if outcome.should_retry:
            raise self.retry(countdown=outcome.retry_after_seconds)
        return attempt.status
    finally:
        db.close()
