"""Celery application. Workflow tasks (order processing, document review)
are added in Phase 2+ under app/tasks/. Kept minimal here so Phase 1 can
prove the worker boots and talks to Redis.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "invoice_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
