"""Local-disk storage adapter — development/Phase-2 default
(`STORAGE_PROVIDER=local`). Not durable, not shared across instances;
production must switch to a real S3/R2/Azure adapter (Phase 3+).
`get_signed_url` here returns a local file:// style path, not a real
signed URL — real signing only matters once objects live in cloud storage.
"""

from __future__ import annotations

from pathlib import Path

from app.services.storage.base import StorageAdapter


class LocalStorageAdapter(StorageAdapter):
    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        path = self._base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get_signed_url(self, key: str, *, expires_in_seconds: int = 3600) -> str:
        return f"file://{(self._base_dir / key).resolve()}"
