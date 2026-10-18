# These tests exercise the background worker independently of the upload endpoint.
# ruff: noqa: SLF001

from asyncio import CancelledError, Event, Semaphore, TaskGroup, wait_for
from contextlib import asynccontextmanager
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import app.services.trace_service as service
from app.models.types import StorageKey, TraceId

_TRACE_ID = TraceId(123)
_OLD_FILE = StorageKey('old.zst')
_NEW_FILE = StorageKey('new.zst')
_ORIGINAL = b'original upload, including any archive wrapper'


@pytest.fixture
def recompression(monkeypatch):
    events = []

    @asynccontextmanager
    async def transaction(*_args):
        events.append('begin')
        yield None
        events.append('commit')

    async def delete(file_id):
        events.append(('delete', file_id))

    storage = SimpleNamespace(
        save=AsyncMock(return_value=_NEW_FILE),
        delete=AsyncMock(side_effect=delete),
    )
    compress = AsyncMock(
        return_value=SimpleNamespace(
            data=b'compressed', suffix='.zst', metadata={'zstd_level': '22'}
        )
    )
    update = AsyncMock(return_value=1)
    report = Mock()
    monkeypatch.setattr(service, 'db', transaction)
    monkeypatch.setattr(service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(service.TraceFile, 'compress', compress)
    monkeypatch.setattr(service, 'db_update', update)
    monkeypatch.setattr(service, 'capture_exception', report)
    return SimpleNamespace(
        events=events, storage=storage, compress=compress, update=update, report=report
    )


async def test_recompress_commits_before_deleting_original(recompression):
    await service._recompress_trace(_TRACE_ID, _OLD_FILE, _ORIGINAL)
    recompression.compress.assert_awaited_once_with(_ORIGINAL, level=22)
    recompression.storage.save.assert_awaited_once_with(
        b'compressed', '.zst', {'zstd_level': '22'}
    )
    recompression.update.assert_awaited_once_with(
        'trace',
        {'file_id': _NEW_FILE},
        where={'id': _TRACE_ID, 'file_id': _OLD_FILE},
        conn=None,
    )
    assert recompression.events == ['begin', 'commit', ('delete', _OLD_FILE)]
    recompression.report.assert_not_called()


async def test_recompress_deleted_trace_cleans_up_new_file(recompression):
    recompression.update.return_value = 0
    await service._recompress_trace(_TRACE_ID, _OLD_FILE, _ORIGINAL)
    recompression.storage.delete.assert_awaited_once_with(_NEW_FILE)
    recompression.report.assert_not_called()


@pytest.mark.parametrize('stage', ['compress', 'save', 'update', 'commit'])
async def test_recompress_failure_preserves_original(recompression, monkeypatch, stage):
    error = RuntimeError('recompression failed')
    if stage == 'commit':

        @asynccontextmanager
        async def transaction(*_args):
            yield None
            raise error

        monkeypatch.setattr(service, 'db', transaction)
    else:
        target = {
            'compress': recompression.compress,
            'save': recompression.storage.save,
            'update': recompression.update,
        }[stage]
        target.side_effect = error

    await service._recompress_trace(_TRACE_ID, _OLD_FILE, _ORIGINAL)
    if stage in {'update', 'commit'}:
        recompression.storage.delete.assert_awaited_once_with(_NEW_FILE)
    else:
        recompression.storage.delete.assert_not_awaited()
    recompression.report.assert_called_once()


async def test_recompress_cancellation_cleans_up_new_file(recompression):
    recompression.update.side_effect = CancelledError
    with pytest.raises(CancelledError):
        await service._recompress_trace(_TRACE_ID, _OLD_FILE, _ORIGINAL)
    recompression.storage.delete.assert_awaited_once_with(_NEW_FILE)
    recompression.report.assert_not_called()


async def test_recompress_cleanup_failure_keeps_committed_file(recompression):
    recompression.storage.delete.side_effect = RuntimeError('storage unavailable')
    await service._recompress_trace(_TRACE_ID, _OLD_FILE, _ORIGINAL)
    recompression.storage.delete.assert_awaited_once_with(_OLD_FILE)
    assert recompression.events == ['begin', 'commit']
    recompression.report.assert_called_once()


async def test_recompress_serializes_heavy_compression(recompression, monkeypatch):
    started, finish, queued = Event(), Event(), Event()
    compress = recompression.compress
    monkeypatch.setattr(service, '_RECOMPRESS_SEMAPHORE', Semaphore(1))

    async def compress_slowly(*_args, **_kwargs):
        started.set()
        await finish.wait()
        return compress.return_value

    async def second_upload():
        queued.set()
        await service._recompress_trace(_TRACE_ID, _OLD_FILE, _ORIGINAL)

    compress.side_effect = compress_slowly
    async with TaskGroup() as tg:
        tg.create_task(service._recompress_trace(_TRACE_ID, _OLD_FILE, _ORIGINAL))
        await wait_for(started.wait(), timeout=1)
        tg.create_task(second_upload())
        try:
            await wait_for(queued.wait(), timeout=1)
            assert compress.await_count == 1
        finally:
            finish.set()
    assert compress.await_count == 2


async def test_delete_locks_file_pointer_until_commit(recompression, monkeypatch):
    fetch = AsyncMock(return_value=_NEW_FILE)
    monkeypatch.setattr(service, 'auth_user', lambda **_kwargs: {'id': 1})
    monkeypatch.setattr(service, 'db_fetchval', fetch)
    monkeypatch.setattr(service, 'db_delete', AsyncMock(return_value=1))
    monkeypatch.setattr(service, 'audit', AsyncMock())
    await service.TraceService.delete(_TRACE_ID)
    query = fetch.await_args.args[1]
    assert 'FOR UPDATE' in ''.join(query.strings)
    assert recompression.events == ['begin', 'commit', ('delete', _NEW_FILE)]


async def test_upload_returns_before_recompression_finishes(recompression, monkeypatch):
    started, finish = Event(), Event()
    request_context = ContextVar('request_context', default=None)
    request_token = request_context.set('request data')

    async def background(*args):
        assert request_context.get() is None
        assert args == (_TRACE_ID, _NEW_FILE, _ORIGINAL)
        assert recompression.events == ['begin', 'commit']
        started.set()
        await finish.wait()

    monkeypatch.setattr(service, '_recompress_trace', background)
    monkeypatch.setattr(service, 'auth_user', lambda **_kwargs: {'id': 1})
    monkeypatch.setattr(service.TraceFile, 'extract', lambda _file: [b'<gpx/>'])
    monkeypatch.setattr(service.XMLToDict, 'parse', lambda _file: {})
    monkeypatch.setattr(
        service.FormatGPX,
        'decode_tracks',
        lambda _tracks: SimpleNamespace(
            size=1, segments=SimpleNamespace(geoms=[]), elevations=[], capture_times=[]
        ),
    )
    monkeypatch.setattr(
        service,
        'TraceInitValidator',
        SimpleNamespace(validate_python=lambda data: data),
    )
    monkeypatch.setattr(service, 'db_insert', AsyncMock(return_value=(_TRACE_ID,)))
    monkeypatch.setattr(service, 'audit', AsyncMock())

    try:
        trace_id = await wait_for(
            service.TraceService.upload(
                _ORIGINAL, name='test.gpx', description='', tags=[], visibility='public'
            ),
            timeout=1,
        )
        assert trace_id == _TRACE_ID
        await wait_for(started.wait(), timeout=1)
        assert not finish.is_set()
        recompression.compress.assert_awaited_once_with(_ORIGINAL)
    finally:
        request_context.reset(request_token)
        finish.set()
        for task in tuple(service._RECOMPRESS_TASKS):
            await task
