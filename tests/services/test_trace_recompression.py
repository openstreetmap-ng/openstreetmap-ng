from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.types import StorageKey, TraceId
from app.services import trace_service
from app.services.trace_service import _recompress


@pytest.mark.parametrize(
    'outcome',
    ['replace', 'deleted', 'database-error', 'no-saving', 'compression-error'],
)
async def test_recompression_preserves_live_archive(monkeypatch, outcome):
    storage = SimpleNamespace(
        save=AsyncMock(return_value=StorageKey('new.zst')), delete=AsyncMock()
    )
    compress = AsyncMock(
        return_value=SimpleNamespace(
            data=b'new', suffix='.zst', metadata={'zstd_level': '22'}
        )
    )
    update = AsyncMock(return_value=int(outcome == 'replace'))
    if outcome == 'database-error':
        update.side_effect = RuntimeError('Database unavailable')
    if outcome == 'compression-error':
        compress.side_effect = RuntimeError('Compression failed')

    @asynccontextmanager
    async def database(*args, **kwargs):
        yield object()

    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_service.TraceFile, 'compress', compress)
    monkeypatch.setattr(trace_service, 'db', database)
    monkeypatch.setattr(trace_service, 'db_update', update)
    await _recompress(
        TraceId(1),
        StorageKey('old.zst'),
        b'original',
        3 if outcome == 'no-saving' else 100,
    )

    compress.assert_awaited_once_with(b'original', level=22)
    if outcome in {'no-saving', 'compression-error'}:
        storage.save.assert_not_awaited()
        storage.delete.assert_not_awaited()
        update.assert_not_awaited()
    else:
        assert update.call_args.kwargs['where'] == {'id': 1, 'file_id': 'old.zst'}
        storage.delete.assert_awaited_once_with(
            'old.zst' if outcome == 'replace' else 'new.zst'
        )
