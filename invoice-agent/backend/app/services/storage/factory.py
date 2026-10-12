from __future__ import annotations

from app.core.config import Settings
from app.services.storage.base import StorageAdapter
from app.services.storage.local import LocalStorageAdapter


def get_storage_adapter(settings: Settings) -> StorageAdapter:
    if settings.storage_provider == "local":
        return LocalStorageAdapter(settings.storage_local_dir)
    raise NotImplementedError(
        f"STORAGE_PROVIDER={settings.storage_provider!r} has no real adapter yet. "
        "Implement one under app/services/storage/ and register it here — "
        "see docs/architecture.md."
    )
