from abc import ABC, abstractmethod

from app.lib.buffered_random import buffered_rand_urlsafe

STORAGE_KEY_MAX_LENGTH = 64


class StorageBase(ABC):
    __slots__ = ('_context',)

    def __init__(self, context: str):
        self._context = context

    def _make_key(self, data: bytes, suffix: str) -> str:
        """
        Generate a key for a file.

        >>> StorageBase('context')._make_key(b'...', '.png')
        'Drmhze6EPcv0fN_81Bj-nA.png'
        """
        result = buffered_rand_urlsafe(32) + suffix
        if len(result) > STORAGE_KEY_MAX_LENGTH:
            raise ValueError(f'Storage key is too long ({len(result)} > {STORAGE_KEY_MAX_LENGTH})')
        return result

    @abstractmethod
    async def load(self, key: str) -> bytes:
        """
        Load a file from storage by key.
        """
        ...

    async def save(self, data: bytes, suffix: str) -> str:
        """
        Save a file to storage and return its key.
        """
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        """
        Delete a key from storage.
        """
        raise NotImplementedError
