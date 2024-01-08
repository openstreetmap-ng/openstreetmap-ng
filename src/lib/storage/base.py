import secrets
from abc import ABC

from src.lib.crypto import hash_urlsafe

STORAGE_KEY_MAX_LENGTH = 64


class StorageBase(ABC):
    _context: str

    def __init__(self, context: str):
        self._context = context

    def _get_key(self, data: bytes, suffix: str, random: bool) -> str:
        """
        Generate a key for a file.

        If random is `False`, the generated key is deterministic.
        """

        if random:  # noqa: SIM108
            result = secrets.token_urlsafe(32) + suffix
        else:
            result = hash_urlsafe(data) + suffix

        if len(result) > STORAGE_KEY_MAX_LENGTH:
            raise RuntimeError(f'Storage key too long: {len(result)} > {STORAGE_KEY_MAX_LENGTH}')

        return result

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
