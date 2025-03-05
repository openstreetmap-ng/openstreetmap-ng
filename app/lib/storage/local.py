from asyncio import get_running_loop
from pathlib import Path
from typing import override

import cython

from app.config import FILE_STORE_DIR
from app.lib.buffered_random import buffered_rand_storage_key
from app.lib.storage.base import StorageBase
from app.models.types import StorageKey


class LocalStorage(StorageBase):
    """Local file storage."""

    __slots__ = ('_base_dir',)

    def __init__(self, dirname: str):
        super().__init__()
        self._base_dir = FILE_STORE_DIR.joinpath(dirname)

    @override
    async def load(self, key: StorageKey) -> bytes:
        path = _get_path(self._base_dir, key)
        loop = get_running_loop()
        return await loop.run_in_executor(None, path.read_bytes)

    @override
    async def save(self, data: bytes, suffix: str) -> StorageKey:
        key = buffered_rand_storage_key(suffix)

        path = _get_path(self._base_dir, key)
        dir = path.parent
        dir.mkdir(parents=True, exist_ok=True)

        temp_path = dir.joinpath(f'.{path.name}.tmp')
        with temp_path.open('xb') as f:
            loop = get_running_loop()
            await loop.run_in_executor(None, f.write, data)
        temp_path.rename(path)

        return key

    @override
    async def delete(self, key: StorageKey) -> None:
        path = _get_path(self._base_dir, key)
        path.unlink(missing_ok=True)


@cython.cfunc
def _get_path(base_dir: Path, key: StorageKey, /) -> Path:
    """Get the path to a file in the storage."""
    return base_dir.joinpath(key[:2], key[2:4], key) if len(key) > 4 else base_dir.joinpath(key)
