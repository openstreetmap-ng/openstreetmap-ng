import gzip
import logging
import zlib
from types import MappingProxyType

import brotli
from fastapi import Request
from humanize import naturalsize
from starlette.middleware.base import BaseHTTPMiddleware

from lib.exceptions import raise_for
from limits import HTTP_BODY_MAX_SIZE, HTTP_COMPRESSED_BODY_MAX_SIZE

_DECOMPRESS_MAP = MappingProxyType(
    {
        'deflate': lambda b: zlib.decompress(b, -zlib.MAX_WBITS),
        'gzip': lambda b: gzip.decompress(b),
        'br': lambda b: brotli.decompress(b),
    }
)


class RequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_encoding = request.headers.get('Content-Encoding')

        # check size with compression
        if content_encoding and (decompressor := _DECOMPRESS_MAP.get(content_encoding)):
            logging.debug('Decompressing %r content-encoding', content_encoding)

            input_size = 0
            chunks = []

            async for chunk in request.stream():
                input_size += len(chunk)
                if input_size > HTTP_COMPRESSED_BODY_MAX_SIZE:
                    raise_for().input_too_big(input_size)
                chunks.append(chunk)

            logging.debug('Compressed request body size: %s', naturalsize(input_size, True))
            request._body = body = decompressor(b''.join(chunks))  # noqa: SLF001
            decompressed_size = len(body)
            logging.debug('Decompressed request body size: %s', naturalsize(decompressed_size, True))

            if decompressed_size > HTTP_BODY_MAX_SIZE:
                raise_for().input_too_big(decompressed_size)

        # check size without compression
        else:
            input_size = 0
            chunks = []

            async for chunk in request.stream():
                input_size += len(chunk)
                if input_size > HTTP_BODY_MAX_SIZE:
                    raise_for().input_too_big(input_size)
                chunks.append(chunk)

            logging.debug('Request body size: %s', naturalsize(input_size, True))
            request._body = b''.join(chunks)  # noqa: SLF001

        return await call_next(request)
