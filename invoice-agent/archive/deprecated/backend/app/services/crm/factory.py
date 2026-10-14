from __future__ import annotations

from app.core.config import Settings
from app.services.crm.base import CRMAdapter
from app.services.crm.mock import MockCRMAdapter


def get_crm_adapter(settings: Settings) -> CRMAdapter:
    if settings.crm_provider == "mock":
        return MockCRMAdapter()
    raise NotImplementedError(
        f"CRM_PROVIDER={settings.crm_provider!r} has no real adapter yet. "
        "Implement one under app/services/crm/ and register it here — "
        "see docs/architecture.md."
    )
