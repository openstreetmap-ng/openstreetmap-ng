import gzip
import logging
import re
from functools import lru_cache
from io import BytesIO

import brotli
import cython
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from zstandard import ZstdCompressor
from zstandard.backend_cffi import ZstdCompressionChunker

from app.limits import (
    COMPRESS_DYNAMIC_BROTLI_QUALITY,
    COMPRESS_DYNAMIC_GZIP_LEVEL,
    COMPRESS_DYNAMIC_MIN_SIZE,
    COMPRESS_DYNAMIC_ZSTD_LEVEL,
)

_zstd_compressor = ZstdCompressor(level=COMPRESS_DYNAMIC_ZSTD_LEVEL)


class CompressMiddleware:
    """
    Response compressing middleware.
    """

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        request_headers = Headers(scope=scope)
        accept_encoding = request_headers.get('Accept-Encoding')

        if not accept_encoding:
            await self.app(scope, receive, send)
            return

        accept_encodings = parse_accept_encoding(accept_encoding)

        if 'zstd' in accept_encodings:
            await ZstdResponder(self.app)(scope, receive, send)
        elif 'br' in accept_encodings:
            await BrotliResponder(self.app)(scope, receive, send)
        elif 'gzip' in accept_encodings:
            await GZipResponder(self.app)(scope, receive, send)
        else:
            await self.app(scope, receive, send)


class ZstdResponder:
    __slots__ = ('app', 'send', 'start_message', 'chunker')

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.send: Send = None
        self.start_message: Message | None = None
        self.chunker: ZstdCompressionChunker | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.send = send
        await self.app(scope, receive, self.wrapper)

    async def wrapper(self, message: Message) -> None:
        message_type: str = message['type']

        # handle start message
        if message_type == 'http.response.start':
            if _is_start_message_satisfied(message):
                # capture start message and wait for response body
                self.start_message = message
                return
            else:
                await self.send(message)
                return

        # skip further processing if not satisfied
        if self.start_message is None:
            await self.send(message)
            return

        # skip unknown messages
        if message_type != 'http.response.body':
            logging.warning('Unsupported ASGI message type %r', message_type)
            await self.send(message)
            return

        body: bytes = message.get('body', b'')
        more_body: cython.char = message.get('more_body', False)

        if self.chunker is None:
            if not _is_body_satisfied(body, more_body):
                await self.send(self.start_message)
                await self.send(message)
                return

            headers = MutableHeaders(raw=self.start_message['headers'])
            headers['Content-Encoding'] = 'zstd'
            headers.add_vary_header('Accept-Encoding')

            if not more_body:
                # one-shot
                compressed_body = _zstd_compressor.compress(body)
                headers['Content-Length'] = str(len(compressed_body))
                message['body'] = compressed_body
                await self.send(self.start_message)
                await self.send(message)
                return

            # begin streaming
            content_length: int = int(headers.get('Content-Length', -1))
            del headers['Content-Length']
            await self.send(self.start_message)
            self.chunker = _zstd_compressor.chunker(content_length)

        # streaming
        for chunk in self.chunker.compress(body):
            await self.send({'type': 'http.response.body', 'body': chunk, 'more_body': True})
        if more_body:
            return
        for chunk in self.chunker.finish():
            await self.send({'type': 'http.response.body', 'body': chunk, 'more_body': True})

        await self.send({'type': 'http.response.body'})


class BrotliResponder:
    __slots__ = ('app', 'send', 'start_message', 'compressor')

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.send: Send = None
        self.start_message: Message | None = None
        self.compressor: brotli.Compressor | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.send = send
        await self.app(scope, receive, self.wrapper)

    async def wrapper(self, message: Message) -> None:
        message_type: str = message['type']

        # handle start message
        if message_type == 'http.response.start':
            if _is_start_message_satisfied(message):
                # capture start message and wait for response body
                self.start_message = message
                return
            else:
                await self.send(message)
                return

        # skip further processing if not satisfied
        if self.start_message is None:
            await self.send(message)
            return

        # skip unknown messages
        if message_type != 'http.response.body':
            logging.warning('Unsupported ASGI message type %r', message_type)
            await self.send(message)
            return

        body: bytes = message.get('body', b'')
        more_body: cython.char = message.get('more_body', False)

        if self.compressor is None:
            if not _is_body_satisfied(body, more_body):
                await self.send(self.start_message)
                await self.send(message)
                return

            headers = MutableHeaders(raw=self.start_message['headers'])
            headers['Content-Encoding'] = 'br'
            headers.add_vary_header('Accept-Encoding')

            if not more_body:
                # one-shot
                compressed_body = brotli.compress(body, quality=COMPRESS_DYNAMIC_BROTLI_QUALITY)
                headers['Content-Length'] = str(len(compressed_body))
                message['body'] = compressed_body
                await self.send(self.start_message)
                await self.send(message)
                return

            # begin streaming
            del headers['Content-Length']
            await self.send(self.start_message)
            self.compressor = brotli.Compressor(quality=COMPRESS_DYNAMIC_BROTLI_QUALITY)

        # streaming
        compressed_body = self.compressor.process(body)
        if compressed_body:
            await self.send({'type': 'http.response.body', 'body': compressed_body, 'more_body': True})
        if more_body:
            return
        compressed_body = self.compressor.finish()
        await self.send({'type': 'http.response.body', 'body': compressed_body})


class GZipResponder:
    __slots__ = ('app', 'send', 'start_message', 'compressor', 'buffer')

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.send: Send = None
        self.start_message: Message | None = None
        self.compressor: gzip.GzipFile | None = None
        self.buffer: BytesIO | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.send = send
        await self.app(scope, receive, self.wrapper)

    async def wrapper(self, message: Message) -> None:
        message_type: str = message['type']

        # handle start message
        if message_type == 'http.response.start':
            if _is_start_message_satisfied(message):
                # capture start message and wait for response body
                self.start_message = message
                return
            else:
                await self.send(message)
                return

        # skip further processing if not satisfied
        if self.start_message is None:
            await self.send(message)
            return

        # skip unknown messages
        if message_type != 'http.response.body':
            logging.warning('Unsupported ASGI message type %r', message_type)
            await self.send(message)
            return

        body: bytes = message.get('body', b'')
        more_body: cython.char = message.get('more_body', False)

        if self.compressor is None:
            if not _is_body_satisfied(body, more_body):
                await self.send(self.start_message)
                await self.send(message)
                return

            headers = MutableHeaders(raw=self.start_message['headers'])
            headers['Content-Encoding'] = 'gzip'
            headers.add_vary_header('Accept-Encoding')

            if not more_body:
                # one-shot
                compressed_body = gzip.compress(body, compresslevel=COMPRESS_DYNAMIC_GZIP_LEVEL)
                headers['Content-Length'] = str(len(compressed_body))
                message['body'] = compressed_body
                await self.send(self.start_message)
                await self.send(message)
                return

            # begin streaming
            del headers['Content-Length']
            await self.send(self.start_message)
            buffer = BytesIO()
            self.buffer = buffer
            self.compressor = gzip.GzipFile(
                mode='wb',
                fileobj=buffer,
                compresslevel=COMPRESS_DYNAMIC_GZIP_LEVEL,
            )
        else:
            # read property once for performance
            buffer = self.buffer

        # streaming
        self.compressor.write(body)
        if not more_body:
            self.compressor.close()
        compressed_body = buffer.getvalue()
        if more_body:
            if compressed_body:
                buffer.seek(0)
                buffer.truncate()
            else:
                return
        await self.send({'type': 'http.response.body', 'body': compressed_body, 'more_body': more_body})


# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Encoding
_accept_encoding_re = re.compile(r'[a-z]{2,8}')


@lru_cache(maxsize=128)
def parse_accept_encoding(accept_encoding: str) -> frozenset[str]:
    """
    Parse the accept encoding header.

    Returns a set of encodings.

    >>> _parse_accept_encoding('br;q=1.0, gzip;q=0.8, *;q=0.1')
    {'br', 'gzip'}
    """
    return frozenset(_accept_encoding_re.findall(accept_encoding))


# Primarily based on:
# https://github.com/h5bp/server-configs-nginx/blob/main/h5bp/web_performance/compression.conf#L38
_compress_content_types: set[str] = {
    'application/atom+xml',
    'application/geo+json',
    'application/gpx+xml',
    'application/javascript',
    'application/x-javascript',
    'application/json',
    'application/ld+json',
    'application/manifest+json',
    'application/rdf+xml',
    'application/rss+xml',
    'application/vnd.mapbox-vector-tile',
    'application/vnd.ms-fontobject',
    'application/wasm',
    'application/x-web-app-manifest+json',
    'application/xhtml+xml',
    'application/xml',
    'font/eot',
    'font/otf',
    'font/ttf',
    'image/bmp',
    'image/svg+xml',
    'image/vnd.microsoft.icon',
    'image/x-icon',
    'text/cache-manifest',
    'text/calendar',
    'text/css',
    'text/html',
    'text/javascript',
    'text/markdown',
    'text/plain',
    'text/xml',
    'text/vcard',
    'text/vnd.rim.location.xloc',
    'text/vtt',
    'text/x-component',
    'text/x-cross-domain-policy',
}


@cython.cfunc
def _is_start_message_satisfied(message: Message) -> cython.char:
    status_code: cython.int = message['status']
    if status_code < 200 or status_code >= 300:
        return False

    headers = Headers(raw=message['headers'])
    if 'Content-Encoding' in headers or 'X-Precompressed' in headers:
        return False

    content_type: str | None = headers.get('Content-Type')
    if content_type is None:
        return True

    basic_content_type = content_type.partition(';')[0].strip()
    return basic_content_type in _compress_content_types


@cython.cfunc
def _is_body_satisfied(body: bytes, more_body: cython.char) -> cython.char:
    return more_body or len(body) >= COMPRESS_DYNAMIC_MIN_SIZE
