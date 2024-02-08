import logging
from typing import override

from anyio import Path
from starlette.responses import FileResponse, Response
from starlette.staticfiles import PathLike, StaticFiles
from starlette.types import Scope

from app.config import TEST_ENV
from app.db import redis
from app.lib.crypto import hash_hex
from app.limits import STATIC_FILES_CACHE_EXPIRE, STATIC_FILES_CACHE_MAX_SIZE
from app.models.msgspec.static_file_cache_meta import StaticFileCacheMeta


class CachingStaticFiles(StaticFiles):
    def __init__(self, directory: PathLike) -> None:
        super().__init__(directory=directory)

    @override
    async def get_response(self, path: str, scope: Scope) -> Response:
        cache_id_hex = hash_hex(path.encode(), context=None)
        redis_key = f'StaticFiles:{cache_id_hex}'

        async with redis() as conn:
            value: bytes | None = await conn.get(redis_key)

            if value is not None:
                logging.debug('Static file cache hit for %r', path)
                meta = StaticFileCacheMeta.from_bytes(value)
                return Response(meta.content, headers=meta.headers, media_type=meta.media_type)

            logging.debug('Static file cache miss for %r', path)
            r = await super().get_response(path, scope)

            # don't cache when in test environment
            if TEST_ENV:
                return r

            # cache only successful file responses
            if not isinstance(r, FileResponse) or r.status_code != 200:
                return r

            # skip caching large files
            if r.stat_result.st_size > STATIC_FILES_CACHE_MAX_SIZE:
                return r

            content = await Path(r.path).read_bytes()
            headers = dict(r.headers)
            media_type = r.media_type
            value = StaticFileCacheMeta(
                content=content,
                headers=headers,
                media_type=media_type,
            ).to_bytes()

            await conn.set(redis_key, value, ex=STATIC_FILES_CACHE_EXPIRE, nx=True)
            return Response(content, headers=headers, media_type=media_type)
