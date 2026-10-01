# ruff: noqa: SLF001

from asyncio import CancelledError, Event, gather
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import trace_service as service


@pytest.fixture
def state(monkeypatch):
    events = []

    @asynccontextmanager
    async def transaction(*args, **kwargs):
        events.append('begin')
        yield object()
        events.append('commit')

    async def remove(key):
        events.append(('delete', key))

    storage = SimpleNamespace(
        save=AsyncMock(return_value='new.zst'), delete=AsyncMock(side_effect=remove)
    )
    monkeypatch.setattr(service, 'db', transaction)
    monkeypatch.setattr(service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(service, 'db_update', AsyncMock(return_value=1))
    monkeypatch.setattr(service, 'capture_exception', Mock())
    return SimpleNamespace(events=events, storage=storage)


async def test_recompression_commits_before_removing_original(state):
    await service._recompress(1, 'old.zst', b'<gpx />')
    service.db_update.assert_awaited_once()
    assert service.db_update.call_args.kwargs['where'] == {
        'id': 1,
        'file_id': 'old.zst',
    }
    assert state.events == ['begin', 'commit', ('delete', 'old.zst')]
    assert state.storage.save.call_args.args[2] == {'zstd_level': '22'}
    service.capture_exception.assert_not_called()


async def test_recompression_discards_copy_when_trace_deleted_or_replaced(state):
    service.db_update.return_value = 0
    await service._recompress(1, 'old.zst', b'<gpx />')
    state.storage.delete.assert_awaited_once_with('new.zst')


async def test_recompression_update_failure_preserves_original(state):
    service.db_update.side_effect = RuntimeError('database unavailable')
    await service._recompress(1, 'old.zst', b'<gpx />')
    state.storage.delete.assert_awaited_once_with('new.zst')
    service.capture_exception.assert_called_once()


async def test_recompression_save_failure_preserves_original(state):
    state.storage.save.side_effect = RuntimeError('storage unavailable')
    await service._recompress(1, 'old.zst', b'<gpx />')
    state.storage.delete.assert_not_awaited()
    service.db_update.assert_not_awaited()
    service.capture_exception.assert_called_once()


async def test_recompression_cancellation_discards_uncommitted_copy(state):
    service.db_update.side_effect = CancelledError
    with pytest.raises(CancelledError):
        await service._recompress(1, 'old.zst', b'<gpx />')
    state.storage.delete.assert_awaited_once_with('new.zst')


async def test_upload_returns_before_recompression_and_after_commit(state, monkeypatch):
    entered = Event()
    release = Event()

    async def recompress(*args):
        assert 'commit' in state.events
        entered.set()
        await release.wait()

    monkeypatch.setattr(service, '_recompress', recompress)
    monkeypatch.setattr(service.TraceFile, 'extract', Mock(return_value=[b'<gpx/>']))
    monkeypatch.setattr(
        service.XMLToDict, 'parse', Mock(return_value={'gpx': {'trk': []}})
    )
    monkeypatch.setattr(
        service.FormatGPX,
        'decode_tracks',
        Mock(
            return_value=SimpleNamespace(
                size=1,
                segments=SimpleNamespace(geoms=[]),
                elevations=[],
                capture_times=[],
            )
        ),
    )
    monkeypatch.setattr(service, 'auth_user', Mock(return_value={'id': 1}))
    monkeypatch.setattr(
        service,
        'TraceInitValidator',
        SimpleNamespace(validate_python=lambda value: value),
    )
    monkeypatch.setattr(service, 'db_insert', AsyncMock(return_value=(1,)))
    monkeypatch.setattr(service, 'audit', AsyncMock())
    try:
        trace_id = await service.TraceService.upload(
            b'<gpx/>', name='test.gpx', description='', tags=[], visibility='private'
        )
        assert trace_id == 1
        assert state.events == ['begin', 'commit']
        await entered.wait()
        assert state.storage.save.call_args.args[2] == {'zstd_level': '6'}
    finally:
        release.set()
        await gather(*service._RECOMPRESSION_TASKS)


async def test_failed_upload_does_not_schedule_recompression(state, monkeypatch):
    monkeypatch.setattr(service.TraceFile, 'extract', Mock(return_value=[b'<gpx/>']))
    monkeypatch.setattr(
        service.XMLToDict, 'parse', Mock(return_value={'gpx': {'trk': []}})
    )
    monkeypatch.setattr(
        service.FormatGPX,
        'decode_tracks',
        Mock(
            return_value=SimpleNamespace(
                size=1,
                segments=SimpleNamespace(geoms=[]),
                elevations=[],
                capture_times=[],
            )
        ),
    )
    monkeypatch.setattr(service, 'auth_user', Mock(return_value={'id': 1}))
    monkeypatch.setattr(
        service,
        'TraceInitValidator',
        SimpleNamespace(validate_python=lambda value: value),
    )
    monkeypatch.setattr(
        service, 'db_insert', AsyncMock(side_effect=RuntimeError('insert failed'))
    )
    monkeypatch.setattr(service, 'create_task', Mock())
    with pytest.raises(RuntimeError, match='insert failed'):
        await service.TraceService.upload(
            b'<gpx/>', name='test.gpx', description='', tags=[], visibility='private'
        )
    service.create_task.assert_not_called()
    state.storage.delete.assert_awaited_once_with('new.zst')
