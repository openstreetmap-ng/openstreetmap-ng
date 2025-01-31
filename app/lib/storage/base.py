from abc import ABC, abstractmethod

from app.lib.buffered_random import buffered_rand_urlsafe
from app.limits import STORAGE_KEY_MAX_LENGTH
from app.models.types import StorageKey


class StorageBase(ABC):
    __slots__ = ('_context',)

    def __init__(self, context: str):
        self._context = context

    def _make_key(self, suffix: str) -> StorageKey:
        """
        Generate a key for a file.

        >>> StorageBase('context')._make_key(b'...', '.png')
        'Drmhze6EPcv0fN_81Bj-nA.png'
        """
        key = buffered_rand_urlsafe(32) + suffix
        if len(key) > STORAGE_KEY_MAX_LENGTH:
            raise ValueError(f'Storage key is too long ({len(key)} > {STORAGE_KEY_MAX_LENGTH})')
        return StorageKey(key)

    @abstractmethod
    async def load(self, key: StorageKey) -> bytes:
        """Load a file from storage by key."""
        ...

    async def save(self, data: bytes, suffix: str) -> StorageKey:
        """Save a file to storage and return its key."""
        raise NotImplementedError

    async def delete(self, key: StorageKey) -> None:
        """Delete a key from storage."""
        raise NotImplementedError
