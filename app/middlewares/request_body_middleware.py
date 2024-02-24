import gzip
import logging
import zlib
from collections.abc import Callable

import brotlicffi
import cython
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.lib.exceptions_context import raise_for
from app.lib.naturalsize import naturalsize
from app.limits import HTTP_BODY_MAX_SIZE, HTTP_COMPRESSED_BODY_MAX_SIZE


@cython.cfunc
def _decompress_deflate(buffer: bytes) -> bytes:
    return zlib.decompress(buffer, -zlib.MAX_WBITS)


@cython.cfunc
def _decompress_gzip(buffer: bytes) -> bytes:
    return gzip.decompress(buffer)


@cython.cfunc
def _decompress_brotli(buffer: bytes) -> bytes:
    return brotlicffi.decompress(buffer)


def _get_decompressor(content_encoding: str | None) -> Callable[[bytes], bytes] | None:
    if content_encoding is None:
        return None

    if content_encoding == 'deflate':
        return _decompress_deflate
    if content_encoding == 'gzip':
        return _decompress_gzip
    if content_encoding == 'br':
        return _decompress_brotli

    return None


class RequestBodyMiddleware(BaseHTTPMiddleware):
    """
    Decompress requests bodies and check their size.
    """

    async def dispatch(self, request: Request, call_next):
        content_encoding: str | None = request.headers.get('Content-Encoding')
        input_size: cython.int = 0
        chunks = []

        # check size with compression
        if (decompressor := _get_decompressor(content_encoding)) is not None:
            logging.debug('Decompressing %r request encoding', content_encoding)

            async for chunk in request.stream():
                input_size += len(chunk)
                if input_size > HTTP_COMPRESSED_BODY_MAX_SIZE:
                    raise_for().input_too_big(input_size)
                chunks.append(chunk)

            request._body = body = decompressor(b''.join(chunks))  # noqa: SLF001
            logging.debug('Request body size: %s -> %s (decompressed)', naturalsize(input_size), naturalsize(len(body)))

            if len(body) > HTTP_BODY_MAX_SIZE:
                raise_for().input_too_big(len(body))

        # check size without compression
        else:
            async for chunk in request.stream():
                input_size += len(chunk)
                if input_size > HTTP_BODY_MAX_SIZE:
                    raise_for().input_too_big(input_size)
                chunks.append(chunk)

            if input_size > 0:
                request._body = b''.join(chunks)  # noqa: SLF001
                logging.debug('Request body size: %s', naturalsize(input_size))
            else:
                request._body = b''  # noqa: SLF001

        return await call_next(request)
