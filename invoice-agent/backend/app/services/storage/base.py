from __future__ import annotations

from abc import ABC, abstractmethod


class StorageAdapter(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes, *, content_type: str = "application/octet-stream") -> str:
        """Persists `data` under `key`. Returns the storage key (unchanged,
        but returned for symmetry with adapters that namespace/prefix it).
        """
        ...

    @abstractmethod
    def get_signed_url(self, key: str, *, expires_in_seconds: int = 3600) -> str:
        ...

    @abstractmethod
    def read(self, key: str) -> bytes:
        ...

    @property
    @abstractmethod
    def supports_direct_streaming(self) -> bool:
        """True for adapters (like local disk) where the API should stream
        bytes itself; False for adapters (like real S3/R2) where the API
        should redirect to a short-lived signed URL instead.
        """
        ...
