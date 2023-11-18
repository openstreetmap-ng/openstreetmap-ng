import secrets
from abc import ABC

from lib.crypto import hash_urlsafe


class StorageBase(ABC):
    _context: str

    def __init__(self, context: str):
        self._context = context

    def _get_key(self, data: bytes, suffix: str, random: bool) -> str:
        """
        Generate a key for a file.

        If random is `False`, the generated key is deterministic.
        """

        if random:
            return secrets.token_urlsafe(32) + suffix
        else:
            return hash_urlsafe(data) + suffix

    async def load(self, key: str) -> bytes:
        """
        Load a file from storage by key string.
        """

        raise NotImplementedError

    async def save(self, data: bytes, suffix: str, *, random: bool = True) -> str:
        """
        Save a file to storage by key string.
        """

        raise NotImplementedError

    async def delete(self, key: str) -> None:
        """
        Delete a key from storage.
        """

        raise NotImplementedError
