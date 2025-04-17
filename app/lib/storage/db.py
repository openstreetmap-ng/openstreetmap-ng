from typing import override

from app.db import db
from app.lib.buffered_random import buffered_rand_storage_key
from app.lib.storage.base import StorageBase
from app.models.types import StorageKey


class DBStorage(StorageBase):
    """Local file storage."""

    __slots__ = ('_context',)

    def __init__(self, context: str):
        super().__init__()
        self._context = context

    @override
    async def load(self, key: StorageKey) -> bytes:
        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT data FROM file
                WHERE context = %s AND key = %s
                """,
                (self._context, key),
            ) as r,
        ):
            row: tuple[bytes] | None = await r.fetchone()
            if row is None:
                raise FileNotFoundError(f'File {key!r} not found in {self._context!r}')
            return row[0]

    @override
    async def save(
        self, data: bytes, suffix: str, metadata: dict[str, str] | None = None
    ) -> StorageKey:
        key = buffered_rand_storage_key(suffix)

        async with db(True) as conn:
            await conn.execute(
                """
                INSERT INTO file (context, key, data, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                (self._context, key, data, metadata),
            )

        return key

    @override
    async def delete(self, key: StorageKey) -> None:
        async with db(True) as conn:
            await conn.execute(
                """
                DELETE FROM file
                WHERE context = %s AND key = %s
                """,
                (self._context, key),
            )
