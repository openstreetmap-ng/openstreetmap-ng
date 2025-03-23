from abc import ABC, abstractmethod

from app.models.types import StorageKey


class StorageBase(ABC):
    __slots__ = ()

    @abstractmethod
    async def load(self, key: StorageKey) -> bytes:
        """Load a file from storage by key."""
        ...

    async def save(self, data: bytes, suffix: str, metadata: dict[str, str] | None = None) -> StorageKey:
        """Save a file to storage and return its key."""
        raise NotImplementedError

    async def delete(self, key: StorageKey) -> None:
        """Delete a key from storage."""
        raise NotImplementedError
