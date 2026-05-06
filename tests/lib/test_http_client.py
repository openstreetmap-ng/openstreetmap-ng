import asyncio
import socket
from typing import override

import pytest
from aiohttp import web
from aiohttp.abc import AbstractResolver, ResolveResult
from multidict import CIMultiDict, CIMultiDictProxy

from app.lib.http_client import (
    HTTPClient,
    HTTPError,
    HTTPResponse,
    SSRFProtectionError,
    _GlobalResolver,
)


class _FakeResolver(AbstractResolver):
    def __init__(self, *hosts: str):
        self.hosts = hosts
        self.closed = False

    @override
    async def resolve(
        self,
        host: str,
        port: int = 0,
        family: socket.AddressFamily = socket.AF_INET,
    ) -> list[ResolveResult]:
        return [
            {
                'hostname': host,
                'host': resolved,
                'port': port,
                'family': family,
                'proto': 0,
                'flags': socket.AI_NUMERICHOST,
            }
            for resolved in self.hosts
        ]

    @override
    async def close(self):
        self.closed = True


def _response(status_code: int, content: bytes):
    return HTTPResponse(
        status_code=status_code,
        headers=CIMultiDictProxy(CIMultiDict({'Content-Type': 'application/json'})),
        content=content,
        url='https://example.com',
        reason='OK' if status_code < 400 else 'Bad Request',
        encoding='utf-8',
    )


def test_http_response_helpers():
    response = _response(200, b'{"ok":true}')

    assert response.is_success
    assert response.text == '{"ok":true}'
    assert response.json() == {'ok': True}
    response.raise_for_status()


def test_http_response_raise_for_status():
    response = _response(400, b'bad')

    with pytest.raises(HTTPError) as e:
        response.raise_for_status()

    assert e.value.response is response


def test_global_resolver_filters_non_global_answers():
    async def run():
        fake = _FakeResolver('10.0.0.1', '8.8.8.8', '64:ff9b::808:808')
        resolver = _GlobalResolver(fake)

        results = await resolver.resolve('example.com', 443)

        assert [r['host'] for r in results] == ['8.8.8.8', '64:ff9b::808:808']
        await resolver.close()
        assert fake.closed

    asyncio.run(run())


def test_global_resolver_rejects_all_non_global_answers():
    async def run():
        resolver = _GlobalResolver(
            _FakeResolver('127.0.0.1', '10.0.0.1', '64:ff9b::c0a8:101')
        )

        with pytest.raises(SSRFProtectionError):
            await resolver.resolve('example.com', 443)

    asyncio.run(run())


def test_http_client_rejects_non_global_ip_literals_before_connect():
    async def run():
        client = HTTPClient(ssrf_protection=True)

        async with client.context():
            with pytest.raises(SSRFProtectionError):
                await client.request('GET', 'http://127.0.0.1/')
            with pytest.raises(SSRFProtectionError):
                await client.request('GET', 'http://[64:ff9b::7f00:1]/')

    asyncio.run(run())


def test_http_client_reads_bounded_response():
    async def handler(_):
        return web.Response(text='hello', charset='utf-8')

    async def run():
        app = web.Application()
        app.router.add_get('/', handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        client = HTTPClient(ssrf_protection=False)

        try:
            async with client.context():
                r = await client.request(
                    'GET',
                    f'http://127.0.0.1:{runner.addresses[0][1]}/',
                    max_bytes=16,
                )
                assert r.text == 'hello'
        finally:
            await runner.cleanup()

    asyncio.run(run())


def test_http_client_does_not_follow_redirects_by_default():
    async def redirect(_):
        raise web.HTTPFound('/target')

    async def target(_):
        return web.Response(text='target')

    async def run():
        app = web.Application()
        app.router.add_get('/', redirect)
        app.router.add_get('/target', target)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        client = HTTPClient(ssrf_protection=False)

        try:
            async with client.context():
                r = await client.request(
                    'GET',
                    f'http://127.0.0.1:{runner.addresses[0][1]}/',
                )
                assert r.status_code == 302

                r = await client.request(
                    'GET',
                    f'http://127.0.0.1:{runner.addresses[0][1]}/',
                    follow_redirects=True,
                )
                assert r.text == 'target'
        finally:
            await runner.cleanup()

    asyncio.run(run())


def test_http_client_rejects_oversized_response():
    async def handler(_):
        return web.Response(body=b'too large')

    async def run():
        app = web.Application()
        app.router.add_get('/', handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        client = HTTPClient(ssrf_protection=False)

        try:
            async with client.context():
                with pytest.raises(HTTPError):
                    await client.request(
                        'GET',
                        f'http://127.0.0.1:{runner.addresses[0][1]}/',
                        max_bytes=4,
                    )
        finally:
            await runner.cleanup()

    asyncio.run(run())
