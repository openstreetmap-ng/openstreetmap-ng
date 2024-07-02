from asyncio import get_running_loop
from pathlib import Path

import cython

from app.config import FILE_STORE_DIR
from app.lib.buffered_random import buffered_randbytes
from app.lib.storage.base import StorageBase


class LocalStorage(StorageBase):
    """
    Local file storage.
    """

    __slots__ = ('_base_dir',)

    def __init__(self, context: str):
        super().__init__(context)
        self._base_dir: Path = FILE_STORE_DIR.joinpath(context)

    async def load(self, key: str) -> bytes:
        path = _get_path(self._base_dir, key)
        loop = get_running_loop()
        return await loop.run_in_executor(None, path.read_bytes)

    async def save(self, data: bytes, suffix: str) -> str:
        key = self._make_key(data, suffix)
        path = _get_path(self._base_dir, key)

        temp_name = f'.{buffered_randbytes(16).hex()}.tmp'
        temp_path = path.with_name(temp_name)

        with temp_path.open('xb') as f:
            loop = get_running_loop()
            await loop.run_in_executor(None, f.write, data)

        temp_path.rename(path)
        return key

    async def delete(self, key: str) -> None:
        path = _get_path(self._base_dir, key)
        path.unlink(missing_ok=True)


@cython.cfunc
def _get_path(base_dir: Path, key: str) -> Path:
    """
    Get the path to a file by key string.

    >>> _get_path(Path('context'), 'file_key.png')
    Path('.../context/file_key.png')
    """
    return base_dir.joinpath(key)
