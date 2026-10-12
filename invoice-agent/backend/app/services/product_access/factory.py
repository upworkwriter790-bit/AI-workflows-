from __future__ import annotations

from app.core.config import Settings
from app.services.product_access.base import ProductAccessAdapter
from app.services.product_access.mock import MockProductAccessAdapter


def get_product_access_adapter(settings: Settings) -> ProductAccessAdapter:
    if settings.product_access_provider == "mock":
        return MockProductAccessAdapter()
    raise NotImplementedError(
        f"PRODUCT_ACCESS_PROVIDER={settings.product_access_provider!r} has no real "
        "adapter yet. Implement one under app/services/product_access/ and "
        "register it here — see docs/architecture.md."
    )
