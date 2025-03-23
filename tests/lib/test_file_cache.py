from datetime import timedelta

import pytest

from app.lib.file_cache import FileCache
from app.models.types import StorageKey


async def test_basic_operations():
    key = StorageKey('test_key')
    data = b'test_value'
    cache = FileCache('test')

    # Set and verify storage
    async with cache.lock(key) as lock:
        await FileCache.set(lock, data, ttl=None)

    result = await cache.get(key)
    assert result == data, f"Expected '{data}', got '{result}'"

    # Delete and verify removal
    cache.delete(key)
    result = await cache.get(key)
    assert result is None, f"Expected None after deletion, got '{result}'"


@pytest.mark.parametrize(
    'ttl,is_deleted',
    [
        (timedelta(hours=1), False),  # Valid TTL, should not be deleted
        (timedelta(seconds=-1), True),  # Expired TTL, should be deleted
        (None, False),  # No TTL, should not be deleted
    ],
)
async def test_ttl_expiration(ttl, is_deleted):
    key = StorageKey('expire_key')
    data = b'test_value'
    cache = FileCache('test')

    # Set cache with specified TTL
    async with cache.lock(key) as lock:
        await FileCache.set(lock, data, ttl=ttl)

    # Verify result based on TTL
    result = await cache.get(key)
    if is_deleted:
        assert result is None, f'With TTL {ttl}, entry must be deleted'
    else:
        assert result == data, f'With TTL {ttl}, entry must not be deleted'


async def test_nonexistent_key():
    key = StorageKey('nonexistent_key')
    cache = FileCache('test')
    result = await cache.get(key)
    assert result is None, f"Expected None for nonexistent key, got '{result}'"


async def test_value_overwrite():
    key = StorageKey('overwrite_key')
    cache = FileCache('test')

    # Set initial value
    async with cache.lock(key) as lock:
        await FileCache.set(lock, b'initial', ttl=None)

    # Verify initial value
    assert await cache.get(key) == b'initial', 'Initial value must be stored correctly'

    # Overwrite with new value
    async with cache.lock(key) as lock:
        await FileCache.set(lock, b'updated', ttl=None)

    # Verify updated value
    result = await cache.get(key)
    assert result == b'updated', f"Expected 'updated', got '{result}'"
