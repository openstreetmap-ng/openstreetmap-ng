import socket
from asyncio import AbstractEventLoop, IncompleteReadError, gather, get_running_loop
from collections.abc import Callable, Coroutine, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from functools import wraps
from ipaddress import IPv4Address, IPv6Address, IPv6Network, ip_address
from typing import Any, Literal, ParamSpec, TypeVar, override
from weakref import WeakKeyDictionary

import cython
import orjson
from aiohttp import (
    ClientError,
    ClientRequest,
    ClientResponse,
    ClientSession,
    ClientTimeout,
    DummyCookieJar,
    TCPConnector,
)
from aiohttp.abc import AbstractResolver, ResolveResult
from aiohttp.client import _RequestOptions
from aiohttp.resolver import DefaultResolver
from multidict import CIMultiDictProxy
from yarl import URL

from app.config import DNS_CACHE_EXPIRE, HTTP_TIMEOUT, USER_AGENT

_P = ParamSpec('_P')
_R = TypeVar('_R')
_IPAddress = IPv4Address | IPv6Address
_NAT64_WELL_KNOWN_PREFIX = IPv6Network('64:ff9b::/96')


class HTTPError(Exception):
    """Base class for project outbound HTTP failures."""

    def __init__(self, message: str, *, response: HTTPResponse | None = None):
        super().__init__(message)
        self.response = response


class SSRFProtectionError(HTTPError):
    """Raised when the public HTTP client would access a non-global address."""

    def __init__(self, host: str, ip: str | None = None):
        message = (
            f'Access denied: host {host!r} resolved to non-global address {ip!r}'
            if ip is not None
            else f'Access denied: host {host!r} did not resolve to a global address'
        )
        super().__init__(message)
        self.host = host
        self.ip = ip


@dataclass(slots=True, frozen=True)
class HTTPResponse:
    status_code: int
    headers: CIMultiDictProxy[str]
    content: bytes
    url: str
    reason: str
    encoding: str

    @property
    def text(self):
        return self.content.decode(self.encoding)

    @property
    def is_success(self):
        return 200 <= self.status_code < 300

    def json(self):
        return orjson.loads(self.content)

    def raise_for_status(self):
        if self.status_code < 400:
            return
        raise HTTPError(
            f'{self.status_code} {self.reason} for url {self.url}',
            response=self,
        )


@cython.cfunc
def _is_global_ip(ip: _IPAddress) -> cython.bint:
    if not ip.is_global:
        return False
    if isinstance(ip, IPv6Address) and ip in _NAT64_WELL_KNOWN_PREFIX:
        return IPv4Address(ip.packed[-4:]).is_global
    return True


class _GlobalResolver(AbstractResolver):
    def __init__(self, resolver: AbstractResolver | None = None):
        self._resolver = resolver or DefaultResolver()

    @override
    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_INET,
    ) -> list[ResolveResult]:
        results = await self._resolver.resolve(host, port, family)
        allowed: list[ResolveResult] = []
        last_blocked: str | None = None

        for result in results:
            resolved = result['host']
            try:
                ip = ip_address(resolved)
            except ValueError as e:
                raise SSRFProtectionError(host, resolved) from e

            if _is_global_ip(ip):
                allowed.append(result)
            else:
                last_blocked = resolved

        if not allowed:
            raise SSRFProtectionError(host, last_blocked)
        return allowed

    @override
    async def close(self):
        await self._resolver.close()


def _json_serialize(data: Any):
    return orjson.dumps(data).decode()


@cython.cfunc
def _timeout_value(
    timeout: float | timedelta | ClientTimeout,
) -> ClientTimeout:
    if isinstance(timeout, ClientTimeout):
        return timeout
    if isinstance(timeout, timedelta):
        return ClientTimeout(total=timeout.total_seconds())
    return ClientTimeout(total=float(timeout))


class HTTPClient:
    def __init__(
        self,
        *,
        ssrf_protection: bool,
        timeout: timedelta = HTTP_TIMEOUT,
    ):
        self._ssrf_protection = ssrf_protection
        self._timeout = ClientTimeout(total=timeout.total_seconds())
        self._sessions: WeakKeyDictionary[AbstractEventLoop, ClientSession]
        self._sessions = WeakKeyDictionary()

    def _session(self):
        loop = get_running_loop()
        session = self._sessions.get(loop)
        if session is None or session.closed:
            connector = TCPConnector(
                resolver=_GlobalResolver() if self._ssrf_protection else None,
                ttl_dns_cache=int(DNS_CACHE_EXPIRE.total_seconds()),
            )
            session = ClientSession(
                connector=connector,
                cookie_jar=DummyCookieJar(),
                headers={'User-Agent': USER_AGENT},
                timeout=self._timeout,
                raise_for_status=False,
                auto_decompress=True,
                trust_env=False,
                json_serialize=_json_serialize,
                middlewares=((self._ssrf_middleware,) if self._ssrf_protection else ()),
            )
            self._sessions[loop] = session
        return session

    async def _ssrf_middleware(self, request: ClientRequest, handler):
        host = request.url.host
        if host is None:
            raise SSRFProtectionError(str(request.url))
        try:
            ip = ip_address(host)
        except ValueError:
            return await handler(request)
        if not _is_global_ip(ip):
            raise SSRFProtectionError(host, str(ip))
        return await handler(request)

    async def request(
        self,
        method: Literal['GET', 'POST'],
        url: str | URL,
        *,
        params: Mapping[str, Any] | None = None,
        data: Any = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | timedelta | ClientTimeout | None = None,
        follow_redirects: bool = False,
        max_bytes: int | None = None,
    ) -> HTTPResponse:
        kwargs: _RequestOptions = {
            'params': params,
            'data': data,
            'json': json,
            'headers': headers,
            'allow_redirects': follow_redirects,
        }
        if timeout is not None:
            kwargs['timeout'] = _timeout_value(timeout)

        try:
            async with self._session().request(method, url, **kwargs) as response:
                return await _read_response(response, max_bytes=max_bytes)
        except HTTPError:
            raise
        except TimeoutError as e:
            raise HTTPError(str(e) or 'HTTP request timed out') from e
        except ClientError as e:
            raise HTTPError(str(e) or type(e).__name__) from e

    async def aclose(self):
        sessions = list(self._sessions.values())
        self._sessions.clear()
        await gather(*(session.close() for session in sessions))

    @asynccontextmanager
    async def context(self):
        try:
            yield self
        finally:
            await self.aclose()


async def _read_response(
    response: ClientResponse,
    *,
    max_bytes: int | None,
) -> HTTPResponse:
    if max_bytes is None:
        content = await response.read()
    else:
        try:
            content = await response.content.readexactly(max_bytes + 1)
        except IncompleteReadError as e:
            content = e.partial
        else:
            raise HTTPError(f'Response body exceeded {max_bytes} bytes')

    return HTTPResponse(
        status_code=response.status,
        headers=response.headers,
        content=content,
        url=str(response.url),
        reason=response.reason or '',
        encoding=response.charset or 'utf-8',
    )


HTTP = HTTPClient(ssrf_protection=True)
HTTP_INTERNAL = HTTPClient(ssrf_protection=False)


def http_context(
    func: Callable[_P, Coroutine[object, object, _R]],
) -> Callable[_P, Coroutine[object, object, _R]]:
    @wraps(func)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs):
        async with HTTP.context():
            return await func(*args, **kwargs)

    return wrapper
