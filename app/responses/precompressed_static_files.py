import logging
import re
import stat
from os import PathLike, stat_result

import cython
from anyio import to_thread
from cachetools import LRUCache
from fastapi import HTTPException
from starlette import status
from starlette.datastructures import Headers
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.config import TEST_ENV

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Encoding
_accept_encoding_re = re.compile(r'[a-z]{2,8}')


@cython.cfunc
def _parse_accept_encoding(accept_encoding: str) -> frozenset[str]:
    """
    Parse the accept encoding header.

    Returns a set of encodings.

    >>> _parse_accept_encoding('br;q=1.0, gzip;q=0.8, *;q=0.1')
    {'br', 'gzip'}
    """

    return frozenset(_accept_encoding_re.findall(accept_encoding))


@cython.cfunc
def _iter_paths(path: str, accept_encoding: str) -> list[str]:
    """
    Returns a list of paths to try for the given path and accept encoding.

    >>> _iter_paths('example.txt', 'br, gzip')
    ['example.txt.br', 'example.txt']
    """

    accept_encoding_set = _parse_accept_encoding(accept_encoding)
    result: list[str] = []

    if 'zstd' in accept_encoding_set:
        result.append(path + '.zst')
    if 'br' in accept_encoding_set:
        result.append(path + '.br')

    result.append(path)
    return result


class PrecompressedStaticFiles(StaticFiles):
    def __init__(self, directory: str | PathLike[str]) -> None:
        super().__init__(directory=directory)
        self._resolve_cache = LRUCache(maxsize=1024)

    async def get_response(self, path: str, scope: Scope) -> Response:
        headers = Headers(scope=scope)
        accept_encoding = headers.get('Accept-Encoding')
        full_path, stat_result = await self._resolve(path, accept_encoding)
        return self.file_response(full_path, stat_result, scope)

    async def _resolve(self, request_path: str, accept_encoding: str | None) -> tuple[str, stat_result]:
        cache_key = (request_path, accept_encoding)
        result = self._resolve_cache.get(cache_key)
        if result is not None:
            return result

        paths = _iter_paths(request_path, accept_encoding) if accept_encoding else (request_path,)

        for path in paths:
            try:
                full_path, stat_result = await to_thread.run_sync(self.lookup_path, path)
            except PermissionError as e:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED) from e
            except OSError:
                raise

            if stat_result is None or not stat.S_ISREG(stat_result.st_mode):
                # skip missing or non-regular files
                continue

            if path == request_path and len(paths) > 1 and not TEST_ENV:
                logging.warning('Precompressed file not found for %r', path)

            result = (full_path, stat_result)
            self._resolve_cache[cache_key] = result
            return result

        raise HTTPException(status.HTTP_404_NOT_FOUND)
