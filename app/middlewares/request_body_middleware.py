import gzip
import logging
import zlib

import brotlicffi
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.libc.exceptions_context import raise_for
from app.libc.naturalsize import naturalsize
from app.limits import HTTP_BODY_MAX_SIZE, HTTP_COMPRESSED_BODY_MAX_SIZE

# map of content-encoding to decompression function
_decompress_map = {
    'deflate': lambda buffer: zlib.decompress(buffer, -zlib.MAX_WBITS),
    'gzip': lambda buffer: gzip.decompress(buffer),
    'br': lambda buffer: brotlicffi.decompress(buffer),
}


class RequestBodyMiddleware(BaseHTTPMiddleware):
    """
    Decompress request body and limit its size.
    """

    async def dispatch(self, request: Request, call_next):
        content_encoding = request.headers.get('content-encoding')

        # check size with compression
        if content_encoding and (decompressor := _decompress_map.get(content_encoding)):
            logging.debug('Decompressing %r content-encoding', content_encoding)

            input_size = 0
            chunks = []

            async for chunk in request.stream():
                input_size += len(chunk)
                if input_size > HTTP_COMPRESSED_BODY_MAX_SIZE:
                    raise_for().input_too_big(input_size)
                chunks.append(chunk)

            logging.debug('Compressed request body size: %s', naturalsize(input_size))
            request._body = body = decompressor(b''.join(chunks))  # noqa: SLF001
            decompressed_size = len(body)
            logging.debug('Decompressed request body size: %s', naturalsize(decompressed_size))

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

            logging.debug('Request body size: %s', naturalsize(input_size))
            request._body = b''.join(chunks)  # noqa: SLF001

        return await call_next(request)
