from asyncio import CancelledError
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.types import StorageKey, TraceId
from app.services import trace_service
from app.services.trace_service import _recompress


@pytest.fixture
def recompression(monkeypatch):
    @asynccontextmanager
    async def transaction(*args, **kwargs):
        yield object()

    compress = AsyncMock(
        return_value=SimpleNamespace(
            data=b'compressed', suffix='.zst', metadata={'zstd_level': '22'}
        )
    )
    storage = SimpleNamespace(
        save=AsyncMock(return_value=StorageKey('new.zst')),
        delete=AsyncMock(),
    )
    update = AsyncMock(return_value=1)
    monkeypatch.setattr(trace_service.TraceFile, 'compress', compress)
    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_service, 'db', transaction)
    monkeypatch.setattr(trace_service, 'db_update', update)
    return compress, storage, update


@pytest.mark.parametrize('updated,removed', [(1, 'old.zst'), (0, 'new.zst')])
async def test_recompress_replacement(recompression, updated, removed):
    compress, storage, update = recompression
    update.return_value = updated
    await _recompress(TraceId(1), StorageKey('old.zst'), b'input', 100)
    compress.assert_awaited_once_with(b'input', level=22)
    assert update.call_args.kwargs['where'] == {'id': 1, 'file_id': 'old.zst'}
    storage.delete.assert_awaited_once_with(removed)


async def test_recompress_keeps_smaller_original(recompression):
    _, storage, update = recompression
    await _recompress(TraceId(1), StorageKey('old.zst'), b'input', 2)
    storage.save.assert_not_awaited()
    storage.delete.assert_not_awaited()
    update.assert_not_awaited()


async def test_recompress_update_failure_preserves_original(recompression):
    _, storage, update = recompression
    update.side_effect = RuntimeError('database unavailable')
    await _recompress(TraceId(1), StorageKey('old.zst'), b'input', 100)
    storage.delete.assert_awaited_once_with('new.zst')


async def test_recompress_failure_preserves_original(recompression):
    compress, storage, update = recompression
    compress.side_effect = RuntimeError('compression failed')
    await _recompress(TraceId(1), StorageKey('old.zst'), b'input', 100)
    storage.save.assert_not_awaited()
    storage.delete.assert_not_awaited()
    update.assert_not_awaited()


async def test_recompress_cancellation_cleans_uncommitted_file(recompression):
    _, storage, update = recompression
    update.side_effect = CancelledError()
    with pytest.raises(CancelledError):
        await _recompress(TraceId(1), StorageKey('old.zst'), b'input', 100)
    storage.delete.assert_awaited_once_with('new.zst')
