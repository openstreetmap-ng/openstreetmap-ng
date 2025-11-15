import logging
import zlib
from io import BytesIO

import brotli
import cython
from fastapi import Response
from sizestr import sizestr
from starlette import status
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from zstandard import DECOMPRESSION_RECOMMENDED_OUTPUT_SIZE, ZstdDecompressor

from app.config import REQUEST_BODY_MAX_SIZE
from app.middlewares.request_context_middleware import get_request


class _TooBigError(ValueError):
    pass


class RequestBodyMiddleware:
    """Request body decompressing and limiting middleware."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        req = get_request()
        input_size: cython.size_t = 0
        buffer = BytesIO()

        async for chunk in req.stream():
            chunk_size: cython.size_t = len(chunk)
            if not chunk_size:
                break

            input_size += chunk_size
            if input_size > REQUEST_BODY_MAX_SIZE:
                return await Response(
                    f'Request body exceeded {sizestr(REQUEST_BODY_MAX_SIZE)}',
                    status.HTTP_413_CONTENT_TOO_LARGE,
                )(scope, receive, send)

            buffer.write(chunk)

        if input_size:
            body = buffer.getvalue()
            content_encoding = req.headers.get('Content-Encoding')
            decompressor = _get_decompressor(content_encoding)

            if decompressor is not None:
                try:
                    body = decompressor(body)
                except _TooBigError:
                    return await Response(
                        f'Decompressed request body exceeded {sizestr(REQUEST_BODY_MAX_SIZE)}',
                        status.HTTP_413_CONTENT_TOO_LARGE,
                    )(scope, receive, send)
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

            else:
                logging.debug(
                    'Request body size: %s',
                    sizestr(input_size),
                )
        else:
            body = b''

        req._body = body  # update shared instance # noqa: SLF001
        wrapper_finished: cython.bint = False

        async def wrapper() -> Message:
            nonlocal wrapper_finished
            if wrapper_finished:
                return await receive()
            wrapper_finished = True
            return {'type': 'http.request', 'body': body}

        return await self.app(scope, wrapper, send)


def _decompress_zstd(
    buffer: bytes,
    *,
    chunk_size: cython.size_t = DECOMPRESSION_RECOMMENDED_OUTPUT_SIZE,
) -> bytes:
    decompressor = ZstdDecompressor().decompressobj()
    chunks: list[bytes] = []
    total_size: cython.size_t = 0

    i: cython.size_t
    for i in range(0, len(buffer), chunk_size):
        chunk = decompressor.decompress(buffer[i : i + chunk_size])
        chunks.append(chunk)
        total_size += len(chunk)
        if total_size > REQUEST_BODY_MAX_SIZE:
            raise _TooBigError

    if not decompressor.eof or decompressor.unused_data:
        raise ValueError('Zstd stream is corrupted')

    return b''.join(chunks)


def _decompress_brotli(
    buffer: bytes,
    *,
    chunk_size: cython.size_t = (1 << 16) - 1,
) -> bytes:
    decompressor = brotli.Decompressor()
    chunks: list[bytes] = []
    total_size: cython.size_t = 0

    i: cython.size_t
    for i in range(0, len(buffer), chunk_size):
        chunk = decompressor.process(buffer[i : i + chunk_size])
        chunks.append(chunk)
        total_size += len(chunk)
        if total_size > REQUEST_BODY_MAX_SIZE:
            raise _TooBigError

    if not decompressor.is_finished():
        raise ValueError('Brotli stream is corrupted')

    return b''.join(chunks)


def _decompress_gzip(buffer: bytes) -> bytes:
    decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
    result = decompressor.decompress(buffer, REQUEST_BODY_MAX_SIZE)

    if decompressor.unconsumed_tail:
        raise _TooBigError
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError('Gzip stream is corrupted')

    return result


def _decompress_zlib(buffer: bytes) -> bytes:
    decompressor = zlib.decompressobj()
    result = decompressor.decompress(buffer, REQUEST_BODY_MAX_SIZE)

    if decompressor.unconsumed_tail:
        raise _TooBigError
    if not decompressor.eof or decompressor.unused_data:
        raise ValueError('Zlib stream is corrupted')

    return result


@cython.cfunc
def _get_decompressor(content_encoding: str | None):
    if content_encoding is None:
        return None
    if content_encoding == 'zstd':
        return _decompress_zstd
    if content_encoding == 'br':
        return _decompress_brotli
    if content_encoding == 'gzip':
        return _decompress_gzip
    if content_encoding == 'deflate':
        return _decompress_zlib
    return None
