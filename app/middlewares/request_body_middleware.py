import gzip
import logging
import zlib
from io import BytesIO

import brotli
import cython
from fastapi import Response
from sizestr import sizestr
from starlette import status
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from zstandard import ZstdDecompressor

from app.config import REQUEST_BODY_MAX_SIZE
from app.middlewares.request_context_middleware import get_request

_ZSTD_DECOMPRESS = ZstdDecompressor().decompress


class RequestBodyMiddleware:
    """Request body decompressing and limiting middleware."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        request = get_request()
        input_size: cython.Py_ssize_t = 0
        buffer = BytesIO()

        async for chunk in request.stream():
            chunk_size: cython.Py_ssize_t = len(chunk)
            if not chunk_size:
                break

            input_size += chunk_size
            if input_size > REQUEST_BODY_MAX_SIZE:
                return await Response(
                    f'Request body exceeded {sizestr(REQUEST_BODY_MAX_SIZE)}',
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )(scope, receive, send)

            buffer.write(chunk)

        if input_size:
            body = buffer.getvalue()
            content_encoding = request.headers.get('Content-Encoding')
            decompressor = _get_decompressor(content_encoding)

            if decompressor is not None:
                try:
                    body = decompressor(body)
                except Exception:
                    return await Response(
                        'Unable to decompress request body',
                        status.HTTP_400_BAD_REQUEST,
                    )(scope, receive, send)

                logging.debug(
                    'Request body size: %s -> %s (compression: %s)',
                    sizestr(input_size),
                    sizestr(len(body)),
                    content_encoding,
                )

                if len(body) > REQUEST_BODY_MAX_SIZE:
                    return await Response(
                        f'Decompressed request body exceeded {sizestr(REQUEST_BODY_MAX_SIZE)}',
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )(scope, receive, send)

            else:
                logging.debug(
                    'Request body size: %s',
                    sizestr(input_size),
                )
        else:
            body = b''

        request._body = body  # update shared instance # noqa: SLF001
        wrapper_finished: cython.bint = False

        async def wrapper() -> Message:
            nonlocal wrapper_finished
            if wrapper_finished:
                return await receive()
            wrapper_finished = True
            return {'type': 'http.request', 'body': body}

        return await self.app(scope, wrapper, send)


@cython.cfunc
def _decompress_zstd(buffer: bytes) -> bytes:
    return _ZSTD_DECOMPRESS(buffer, allow_extra_data=False)


@cython.cfunc
def _get_decompressor(content_encoding: str | None):
    if content_encoding is None:
        return None
    if content_encoding == 'zstd':
        return _decompress_zstd
    if content_encoding == 'br':
        return brotli.decompress
    if content_encoding == 'gzip':
        return gzip.decompress
    if content_encoding == 'deflate':
        return zlib.decompress
    return None
