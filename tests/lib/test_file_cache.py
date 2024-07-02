from datetime import timedelta

import anyio
import pytest

from app.lib.file_cache import FileCache

pytestmark = pytest.mark.anyio


async def test_file_cache():
    cache = FileCache('test')
    await cache.set('key', b'value', ttl=None)
    assert await cache.get('key') == b'value'
    cache.delete('key')
    assert await cache.get('key') is None


async def test_file_cache_expire():
    cache = FileCache('test')
    await cache.set('key', b'value', ttl=timedelta())
    await anyio.sleep(1)
    assert await cache.get('key') is None
