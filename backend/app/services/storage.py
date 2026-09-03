"""Object-storage abstraction.

Local filesystem in development; the interface is S3-compatible in shape so a
cloud backend can be added without touching callers. Stored objects are
addressed by a relative key and served through the API at /api/files/{key}.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()


class ObjectStorage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes) -> str:
        """Store bytes under key, return the key."""

    @abstractmethod
    def get(self, key: str) -> bytes:
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def path(self, key: str) -> Path | None:
        """Local filesystem path if available (for streaming responses)."""


class LocalStorage(ObjectStorage):
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        p = (self.root / key.lstrip("/")).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("Invalid storage key")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._resolve(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def path(self, key: str) -> Path | None:
        p = self._resolve(key)
        return p if p.exists() else None


_storage: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage
