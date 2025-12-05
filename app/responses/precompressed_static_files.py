import stat
from collections import OrderedDict
from functools import lru_cache
from mimetypes import guess_type
from os import PathLike
from os import stat_result as StatResultType  # noqa: N812
from typing import override

import cython
from fastapi import HTTPException
from starlette import status
from starlette.datastructures import Headers
from starlette.responses import FileResponse, Response
from starlette.staticfiles import NotModifiedResponse, StaticFiles
from starlette.types import Scope
from starlette_compress._utils import parse_accept_encoding

from app.config import ENV, STATIC_PRECOMPRESSED_CACHE_MAX_ENTRIES

_CacheKey = tuple[str, str | None]
_CacheValue = tuple[str, StatResultType, str | None]


class PrecompressedStaticFiles(StaticFiles):
    def __init__(self, directory: str | PathLike[str]):
        super().__init__(directory=directory)
        self._resolve_cache = OrderedDict[_CacheKey, _CacheValue]()

    @override
    async def get_response(self, path: str, scope: Scope) -> Response:
        request_headers = Headers(scope=scope)
        accept_encoding = request_headers.get('Accept-Encoding')
        full_path, stat_result, encoding = self._resolve(path, accept_encoding)

        media_type = _guess_media_type(path)
        response = FileResponse(
            full_path,
            media_type=media_type,
            stat_result=stat_result,
        )
        response_headers = response.headers
        response_headers.add_vary_header('Accept-Encoding')

        if self.is_not_modified(response_headers, request_headers):
            return NotModifiedResponse(response_headers)

        if encoding is not None:
            response_headers['Content-Encoding'] = encoding

        response_headers['X-Precompressed'] = '1'
        return response

    def _resolve(self, request_path: str, accept_encoding: str | None) -> _CacheValue:
        cache_key: _CacheKey = (request_path, accept_encoding)
        result = self._resolve_cache.get(cache_key)

        # Use cache unless in dev (support live reload)
        if result is not None and ENV != 'dev':
            self._resolve_cache.move_to_end(cache_key)
            return result

        paths = (
            _try_paths(request_path, accept_encoding)
            if accept_encoding
            else [(request_path, None)]
        )
        for path, encoding in paths:
            try:
                full_path, stat_result = self.lookup_path(path)
            except PermissionError as e:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED) from e

            if stat_result is None or not stat.S_ISREG(stat_result.st_mode):
                # skip missing or non-regular files
                continue

            result = (full_path, stat_result, encoding)
            self._resolve_cache[cache_key] = result
            self._resolve_cache.move_to_end(cache_key)
            if len(self._resolve_cache) > STATIC_PRECOMPRESSED_CACHE_MAX_ENTRIES:
                self._resolve_cache.popitem(False)
            return result

        raise HTTPException(status.HTTP_404_NOT_FOUND)


@lru_cache(maxsize=512)
def _guess_media_type(path: str) -> str:
    return guess_type(path)[0] or 'text/plain'


@cython.cfunc
def _try_paths(path: str, accept_encoding: str) -> list[tuple[str, str | None]]:
    """
    Returns a list of (path, encoding) tuples to try.

    >>> _try_paths('example.txt', 'br, gzip')
    [('example.txt.br', 'br'), ('example.txt', None)]
    """
    accept_encodings = parse_accept_encoding(accept_encoding)
    result: list[tuple[str, str | None]] = []

    if 'zstd' in accept_encodings:
        result.append((path + '.zst', 'zstd'))
    if 'br' in accept_encodings:
        result.append((path + '.br', 'br'))

    result.append((path, None))
    return result
