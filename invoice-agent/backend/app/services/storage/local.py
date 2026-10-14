"""Local-disk storage adapter (`STORAGE_PROVIDER=local`, the default).
Not durable, not shared across instances — production should switch to a
real S3-compatible adapter via `STORAGE_PROVIDER=s3`. `get_signed_url`
here returns a local file:// path, not a real signed URL.
"""

from __future__ import annotations

from pathlib import Path

from app.services.storage.base import StorageAdapter


class LocalStorageAdapter(StorageAdapter):
    supports_direct_streaming = True

    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        path = self._base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        return (self._base_dir / key).read_bytes()

    def get_signed_url(self, key: str, *, expires_in_seconds: int = 3600) -> str:
        return f"file://{(self._base_dir / key).resolve()}"
