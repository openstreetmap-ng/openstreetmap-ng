import logging
from typing import override

from anyio import Path
from starlette.responses import FileResponse, Response
from starlette.staticfiles import PathLike, StaticFiles
from starlette.types import Scope

from app.db import redis
from app.lib.crypto import hash_hex
from app.limits import STATIC_FILES_CACHE_EXPIRE, STATIC_FILES_CACHE_MAX_SIZE
from app.utils import MSGPACK_DECODE, MSGPACK_ENCODE


class CachingStaticFiles(StaticFiles):
    def __init__(self, directory: PathLike) -> None:
        super().__init__(directory=directory)

    @override
    async def get_response(self, path: str, scope: Scope) -> Response:
        cache_id_hex = hash_hex(path.encode(), context=None)
        redis_key = f'StaticFiles:{cache_id_hex}'

        async with redis() as conn:
            value: dict = await conn.hgetall(redis_key)

            if len(value) > 0:
                logging.debug('Static file cache hit for %r', path)
                content: bytes = value[b'content']
                headers: dict[str, str] = MSGPACK_DECODE(value[b'headers'])
                media_type: str = value[b'media_type']
                return Response(content, headers=headers, media_type=media_type)

            logging.debug('Static file cache miss for %r', path)
            r = await super().get_response(path, scope)

            # cache only successful file responses
            if not isinstance(r, FileResponse) or r.status_code != 200:
                return r

            # skip caching large files
            if r.stat_result.st_size > STATIC_FILES_CACHE_MAX_SIZE:
                return r

            content = await Path(r.path).read_bytes()
            headers = dict(r.headers)
            media_type = r.media_type
            value = {
                b'content': content,
                b'headers': MSGPACK_ENCODE(headers),
                b'media_type': media_type,
            }

            pipe = conn.pipeline()
            pipe.hset(redis_key, mapping=value)
            pipe.expire(redis_key, STATIC_FILES_CACHE_EXPIRE, nx=True)
            await pipe.execute()

            return Response(content, headers=headers, media_type=media_type)
