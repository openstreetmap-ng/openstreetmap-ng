from typing import LiteralString, override

from app.db import db_delete, db_fetchval, db_insert
from app.lib.storage.base import StorageBase
from app.models.types import StorageKey
from speedup import buffered_rand_storage_key


class DBStorage(StorageBase):
    """Local file storage."""

    __slots__ = ('_context',)

    def __init__(self, context: str):
        super().__init__()
        self._context = context

    @override
    async def load(self, key: StorageKey):
        context = self._context
        data = await db_fetchval(
            bytes,
            t"""
                SELECT data FROM file
                WHERE context = {context} AND key = {key}
            """,
        )
        if data is None:
            raise FileNotFoundError(f'File {key!r} not found in {self._context!r}')
        return data

    @override
    async def save(
        self, data: bytes, suffix: LiteralString, metadata: dict[str, str] | None = None
    ):
        context = self._context
        key = buffered_rand_storage_key(suffix)

        await db_insert(
            'file',
            {
                'context': context,
                'key': key,
                'data': data,
                'metadata': metadata,
            },
        )

        return key

    @override
    async def delete(self, key: StorageKey):
        context = self._context
        await db_delete(
            'file',
            where={'context': context, 'key': key},
        )
