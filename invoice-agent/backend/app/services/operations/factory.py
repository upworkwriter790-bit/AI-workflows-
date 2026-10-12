from __future__ import annotations

from app.core.config import Settings
from app.services.operations.base import OperationsAdapter
from app.services.operations.mock import MockOperationsAdapter


def get_operations_adapter(settings: Settings) -> OperationsAdapter:
    if settings.operations_notification_provider == "mock":
        return MockOperationsAdapter()
    raise NotImplementedError(
        f"OPERATIONS_NOTIFICATION_PROVIDER={settings.operations_notification_provider!r} "
        "has no real adapter yet. Implement one under app/services/operations/ "
        "and register it here — see docs/architecture.md."
    )
