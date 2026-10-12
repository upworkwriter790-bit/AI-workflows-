from __future__ import annotations

from app.core.config import Settings
from app.services.erp.base import ERPAdapter
from app.services.erp.mock import MockERPAdapter


def get_erp_adapter(settings: Settings) -> ERPAdapter:
    if settings.erp_provider == "mock":
        return MockERPAdapter()
    raise NotImplementedError(
        f"ERP_PROVIDER={settings.erp_provider!r} has no real adapter yet. "
        "Implement one under app/services/erp/ and register it here — "
        "see docs/architecture.md."
    )
