from datetime import timedelta

from app.lib.file_cache import FileCache


async def test_file_cache():
    cache = FileCache('test')
    await cache.set('key', b'value', ttl=None)
    assert await cache.get('key') == b'value'
    cache.delete('key')
    assert await cache.get('key') is None


async def test_file_cache_expire():
    cache = FileCache('test')
    await cache.set('key', b'value', ttl=timedelta(seconds=-2))
    assert await cache.get('key') is None
