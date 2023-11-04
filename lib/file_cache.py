from anyio import Path

from config import FILE_CACHE_DIR


class FileCache:
    _context: str

    def __init__(self, context: str):
        self._context = context

    async def _get_path(self, key: str) -> Path:
        d1 = key[:1]
        d2 = key[1:3]
        dir = FILE_CACHE_DIR / self._context / d1 / d2
        await dir.mkdir(parents=True, exist_ok=True)
        return dir / key

    async def get(self, key: str) -> bytes | None:
        try:
            path = await self._get_path(key)
            return await path.read_bytes()
        except OSError:
            return None

    # TODO: TTL Support
    async def set(self, key: str, data: bytes) -> None:
        path = await self._get_path(key)
        async with await path.open('xb') as f:
            await f.write(data)

    async def pop(self, key: str) -> None:
        path = await self._get_path(key)
        await path.unlink(missing_ok=True)

    async def clean(self):
        # TODO: implement cleaning logic here, using Lock for distributed-process safety
        pass
