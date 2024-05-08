from abc import ABC, abstractmethod

from app.lib.buffered_random import buffered_rand_urlsafe
from app.lib.crypto import hash_urlsafe

STORAGE_KEY_MAX_LENGTH = 64


class StorageBase(ABC):
    __slots__ = ('_context',)

    def __init__(self, context: str):
        self._context = context

    def _make_key(self, data: bytes, suffix: str, random: bool) -> str:
        """
        Generate a key for a file.

        If random is `False`, the generated key is deterministic.

        >>> StorageBase('context')._make_key(b'...', '.png', random=True)
        'Drmhze6EPcv0fN_81Bj-nA.png'
        """

        if random:
            result = buffered_rand_urlsafe(32) + suffix
        else:
            result = hash_urlsafe(data) + suffix

        if len(result) > STORAGE_KEY_MAX_LENGTH:
            raise ValueError(f'Storage key is too long ({len(result)} > {STORAGE_KEY_MAX_LENGTH})')

        return result

    @abstractmethod
    async def load(self, key: str) -> bytes:
        """
        Load a file from storage by key.
        """
        ...

    async def save(self, data: bytes, suffix: str, *, random: bool = True) -> str:
        """
        Save a file to storage and return its key.
        """
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        """
        Delete a key from storage.
        """
        raise NotImplementedError
