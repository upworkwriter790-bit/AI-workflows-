from __future__ import annotations

from app.core.config import Settings
from app.services.email.base import EmailAdapter
from app.services.email.mock import MockEmailAdapter


def get_email_adapter(settings: Settings) -> EmailAdapter:
    if settings.email_provider == "mock":
        return MockEmailAdapter()
    raise NotImplementedError(
        f"EMAIL_PROVIDER={settings.email_provider!r} has no real adapter yet. "
        "Implement one under app/services/email/ and register it here — "
        "see docs/architecture.md."
    )
