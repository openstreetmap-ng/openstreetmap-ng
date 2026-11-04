from asyncio import Event, wait_for
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import trace_service
from app.services.trace_service import _RECOMPRESS_TASKS, _recompress


@pytest.fixture
def dependencies(monkeypatch):
    state = SimpleNamespace(committed=False)

    @asynccontextmanager
    async def transaction(*args, **kwargs):
        yield object()
        state.committed = True

    state.storage = SimpleNamespace(
        save=AsyncMock(return_value='new.zst'), delete=AsyncMock()
    )
    state.update = AsyncMock(return_value=1)
    state.capture = Mock()
    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', state.storage)
    monkeypatch.setattr(trace_service, 'db_update', state.update)
    monkeypatch.setattr(trace_service, 'capture_exception', state.capture)
    monkeypatch.setattr(trace_service, 'db', transaction)
    return state


@pytest.fixture
def compression(monkeypatch):
    compress = AsyncMock(
        return_value=SimpleNamespace(
            data=b'zst', suffix='.zst', metadata={'zstd_level': '22'}
        )
    )
    monkeypatch.setattr(trace_service.TraceFile, 'compress', compress)
    return compress


@pytest.mark.parametrize('rowcount', [0, 1])
async def test_recompress_swaps_only_current_file(dependencies, compression, rowcount):
    dependencies.update.return_value = rowcount
    await _recompress(123, 'old.zst', b'original', 10)

    compression.assert_awaited_once_with(b'original', level=22)
    dependencies.storage.save.assert_awaited_once_with(
        b'zst', '.zst', {'zstd_level': '22'}
    )
    dependencies.update.assert_awaited_once_with(
        'trace', {'file_id': 'new.zst'}, where={'id': 123, 'file_id': 'old.zst'}
    )
    dependencies.storage.delete.assert_awaited_once_with(
        'old.zst' if rowcount else 'new.zst'
    )
    dependencies.capture.assert_not_called()


@pytest.mark.parametrize('size', [2, 3])
async def test_recompress_keeps_original_without_size_saving(
    dependencies, compression, size
):
    await _recompress(123, 'old.zst', b'original', size)
    dependencies.storage.save.assert_not_awaited()
    dependencies.update.assert_not_awaited()
    dependencies.storage.delete.assert_not_awaited()


async def test_recompress_cleans_new_file_after_update_error(dependencies, compression):
    dependencies.update.side_effect = RuntimeError('database unavailable')
    await _recompress(123, 'old.zst', b'original', 10)
    dependencies.storage.delete.assert_awaited_once_with('new.zst')
    dependencies.capture.assert_called_once()


@pytest.mark.parametrize('stage', ['compress', 'save'])
async def test_recompress_failure_preserves_original(dependencies, compression, stage):
    failing = compression if stage == 'compress' else dependencies.storage.save
    failing.side_effect = RuntimeError('background failure')
    await _recompress(123, 'old.zst', b'original', 10)
    dependencies.update.assert_not_awaited()
    dependencies.storage.delete.assert_not_awaited()
    dependencies.capture.assert_called_once()


async def test_recompress_cleanup_error_does_not_delete_live_replacement(
    dependencies, compression
):
    dependencies.storage.delete.side_effect = RuntimeError('storage unavailable')
    await _recompress(123, 'old.zst', b'original', 10)
    dependencies.storage.delete.assert_awaited_once_with('old.zst')
    dependencies.capture.assert_called_once()


@pytest.fixture
def upload_dependencies(monkeypatch, dependencies, compression):
    decoded = SimpleNamespace(
        size=1, segments=SimpleNamespace(geoms=[1]), elevations=None, capture_times=None
    )
    monkeypatch.setattr(trace_service, 'auth_user', lambda **_kwargs: {'id': 7})
    monkeypatch.setattr(trace_service.TraceFile, 'extract', lambda data: [data])
    monkeypatch.setattr(trace_service.XMLToDict, 'parse', lambda _data: {'gpx': {}})
    monkeypatch.setattr(
        trace_service.FormatGPX, 'decode_tracks', lambda _tracks: decoded
    )
    monkeypatch.setattr(
        trace_service,
        'TraceInitValidator',
        SimpleNamespace(validate_python=lambda x: x),
    )
    monkeypatch.setattr(trace_service, 'db_insert', AsyncMock(return_value=(123,)))
    monkeypatch.setattr(trace_service, 'audit', AsyncMock())
    return dependencies


async def test_upload_starts_background_work_after_commit(
    monkeypatch, upload_dependencies, compression
):
    started = Event()
    finish = Event()

    async def recompress(trace_id, file_id, buffer, compressed_size):
        assert upload_dependencies.committed
        assert (trace_id, file_id, buffer, compressed_size) == (
            123,
            'new.zst',
            b'gpx',
            3,
        )
        started.set()
        await finish.wait()

    monkeypatch.setattr(trace_service, '_recompress', recompress)
    trace_id = await trace_service.TraceService.upload(
        b'gpx', name='test.gpx', description='', tags=[], visibility='public'
    )
    assert trace_id == 123
    compression.assert_awaited_once_with(b'gpx')
    await wait_for(started.wait(), 1)
    tasks = tuple(_RECOMPRESS_TASKS)
    assert tasks and not all(task.done() for task in tasks)
    finish.set()
    for task in tasks:
        await task


async def test_failed_upload_does_not_schedule_recompression(
    monkeypatch, upload_dependencies
):
    recompress = AsyncMock()
    monkeypatch.setattr(trace_service, '_recompress', recompress)
    monkeypatch.setattr(
        trace_service, 'audit', AsyncMock(side_effect=RuntimeError('audit failed'))
    )
    with pytest.raises(RuntimeError, match='audit failed'):
        await trace_service.TraceService.upload(
            b'gpx', name='test.gpx', description='', tags=[], visibility='public'
        )
    recompress.assert_not_called()
    upload_dependencies.storage.delete.assert_awaited_once_with('new.zst')


async def test_delete_removes_file_returned_by_delete(monkeypatch, dependencies):
    monkeypatch.setattr(trace_service, 'auth_user', lambda **_kwargs: {'id': 7})
    monkeypatch.setattr(trace_service, 'db_fetchval', AsyncMock(return_value='old.zst'))
    delete = AsyncMock(return_value=('replacement.zst',))
    monkeypatch.setattr(trace_service, 'db_delete', delete)
    monkeypatch.setattr(trace_service, 'audit', AsyncMock())

    await trace_service.TraceService.delete(123)

    assert delete.await_args.kwargs['returning'] == 'file_id'
    dependencies.storage.delete.assert_awaited_once_with('replacement.zst')
    assert dependencies.committed


async def test_commit_failure_cleans_upload_without_background_work(
    monkeypatch, upload_dependencies
):
    @asynccontextmanager
    async def failed_commit(*args, **kwargs):
        yield object()
        raise RuntimeError('commit failed')

    recompress = AsyncMock()
    monkeypatch.setattr(trace_service, 'db', failed_commit)
    monkeypatch.setattr(trace_service, '_recompress', recompress)
    with pytest.raises(RuntimeError, match='commit failed'):
        await trace_service.TraceService.upload(
            b'gpx', name='test.gpx', description='', tags=[], visibility='public'
        )
    recompress.assert_not_called()
    upload_dependencies.storage.delete.assert_awaited_once_with('new.zst')


async def test_denied_delete_preserves_file(monkeypatch, dependencies):
    monkeypatch.setattr(trace_service, 'auth_user', lambda **_kwargs: {'id': 7})
    monkeypatch.setattr(trace_service, 'db_fetchval', AsyncMock(return_value='old.zst'))
    monkeypatch.setattr(trace_service, 'db_delete', AsyncMock(return_value=None))
    monkeypatch.setattr(
        trace_service,
        'raise_for',
        SimpleNamespace(trace_access_denied=Mock(side_effect=PermissionError)),
    )
    with pytest.raises(PermissionError):
        await trace_service.TraceService.delete(123)
    dependencies.storage.delete.assert_not_awaited()
