from __future__ import annotations

from app.core.config import Settings
from app.services.email.base import EmailProvider
from app.services.email.mock import MockEmailProvider


def get_email_provider(settings: Settings) -> EmailProvider:
    if settings.email_provider == "mock":
        return MockEmailProvider()
    raise NotImplementedError(
        f"EMAIL_PROVIDER={settings.email_provider!r} has no real adapter yet. "
        "Implement one under app/services/email/ matching EmailProvider and "
        "register it here — see docs/architecture.md."
    )
