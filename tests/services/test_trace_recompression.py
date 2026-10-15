# Direct worker calls allow deterministic transaction and storage fault injection.
# ruff: noqa: SLF001
from asyncio import CancelledError, Event, Lock, create_task, gather, sleep, wait_for
from compression import zstd
from contextlib import asynccontextmanager
from contextvars import ContextVar
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey, TraceId
from app.queries import trace_query
from app.services import trace_service

_DATA = b'<gpx><trk><name>round trip</name></trk></gpx>'
_ORIGINAL = StorageKey('original.zst')
_REPLACEMENT = StorageKey('replacement.zst')


class _Backend:
    def __init__(self):
        self.current = _ORIGINAL
        self.files = {_ORIGINAL: zstd.compress(_DATA)}
        self.metadata = {}
        self.next_id = _REPLACEMENT
        self.events = []
        self.commit_error = None
        self.reconcile_error = False
        self.save_error = False
        self.delete_error = False
        self.lock = Lock()

    @asynccontextmanager
    async def db(self, write=True):
        assert write
        async with self.lock:
            conn = SimpleNamespace(pending=self.current)
            self.events.append('begin')
            yield conn
            mode = self.commit_error
            self.commit_error = None
            if mode == 'before':
                raise OSError('commit failed before applying')
            self.current = conn.pending
            self.events.append('commit')
            if mode == 'after':
                raise OSError('commit applied but acknowledgement lost')

    async def update(self, table, values, *, where, conn):
        assert table == 'trace'
        assert where == {'id': 1, 'file_id': _ORIGINAL}
        if conn.pending != _ORIGINAL:
            return 0
        conn.pending = values['file_id']
        self.events.append('update')
        return 1

    async def fetchval(self, value_type, query, *, for_update=False, conn):
        assert for_update
        if self.reconcile_error:
            raise OSError('database unavailable for reconciliation')
        return conn.pending

    async def insert(self, table, values, *, returning, conn):
        assert table == 'trace' and returning == 'id'
        conn.pending = values['file_id']
        self.events.append('insert')
        return (TraceId(1),)

    async def delete_row(self, table, *, where, conn):
        assert table == 'trace' and where == {'id': 1, 'user_id': 7}
        conn.pending = None
        return 1

    async def save(self, data, suffix, metadata):
        if self.save_error:
            raise OSError('storage unavailable')
        key = self.next_id
        self.next_id = _REPLACEMENT
        self.files[key] = data
        self.metadata[key] = metadata.copy()
        self.events.append(('save', key))
        return key

    async def delete(self, key):
        assert self.current != key, 'A referenced file must never be removed'
        self.events.append(('delete', key))
        if self.delete_error:
            raise OSError('delete failed')
        self.files.pop(key, None)

    async def load(self, key):
        self.events.append(('load', key))
        return self.files[key]


@pytest.fixture
def backend(monkeypatch):
    backend = _Backend()
    monkeypatch.setattr(trace_service, 'db', backend.db)
    monkeypatch.setattr(trace_service, 'db_update', backend.update)
    monkeypatch.setattr(trace_service, 'db_fetchval', backend.fetchval)
    monkeypatch.setattr(trace_service, 'db_insert', backend.insert)
    monkeypatch.setattr(trace_service, 'db_delete', backend.delete_row)
    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', backend)
    monkeypatch.setattr(trace_service, 'audit', AsyncMock())
    monkeypatch.setattr(trace_service, 'auth_user', lambda **_kw: {'id': 7})
    monkeypatch.setattr(trace_query, 'TRACE_STORAGE', backend)
    return backend


async def test_recompress_commits_before_deleting_original(backend):
    await trace_service._recompress(TraceId(1), _ORIGINAL, _DATA)
    assert backend.current == _REPLACEMENT
    assert backend.metadata[_REPLACEMENT] == {'zstd_level': '22'}
    assert zstd.decompress(backend.files[_REPLACEMENT]) == _DATA
    assert _ORIGINAL not in backend.files
    assert backend.events.index('commit') < backend.events.index(('delete', _ORIGINAL))


@pytest.mark.parametrize('current', [None, StorageKey('another.zst')])
async def test_recompress_does_not_restore_deleted_or_changed_trace(backend, current):
    backend.current = current

    # Keep save keys distinct from the original even when the trace was deleted.
    async def save(data, suffix, metadata):
        backend.files[_REPLACEMENT] = data
        return _REPLACEMENT

    backend.save = save
    await trace_service._recompress(TraceId(1), _ORIGINAL, _DATA)
    assert backend.current == current
    assert _REPLACEMENT not in backend.files


@pytest.mark.parametrize('stage', ['compress', 'save'])
async def test_recompress_failure_keeps_initial_file(backend, monkeypatch, stage):
    if stage == 'compress':
        monkeypatch.setattr(
            TraceFile, 'compress', AsyncMock(side_effect=OSError('compress'))
        )
    else:
        backend.save_error = True
    await trace_service._recompress(TraceId(1), _ORIGINAL, _DATA)
    assert backend.current == _ORIGINAL
    assert _ORIGINAL in backend.files


@pytest.mark.parametrize('mode', ['before', 'after'])
async def test_recompress_reconciles_uncertain_commit(backend, mode):
    backend.commit_error = mode
    await trace_service._recompress(TraceId(1), _ORIGINAL, _DATA)
    referenced = _ORIGINAL if mode == 'before' else _REPLACEMENT
    assert backend.current == referenced
    assert set(backend.files) == {referenced}


async def test_recompress_retains_files_if_reconciliation_fails(backend):
    backend.commit_error = 'after'
    backend.reconcile_error = True
    await trace_service._recompress(TraceId(1), _ORIGINAL, _DATA)
    assert backend.current == _REPLACEMENT
    assert set(backend.files) == {_ORIGINAL, _REPLACEMENT}


async def test_old_file_cleanup_failure_keeps_replacement(backend):
    backend.delete_error = True
    await trace_service._recompress(TraceId(1), _ORIGINAL, _DATA)
    assert backend.current == _REPLACEMENT
    assert _REPLACEMENT in backend.files
    assert ('delete', _REPLACEMENT) not in backend.events


async def test_cancelled_recompression_cleans_only_unreferenced_file(
    backend, monkeypatch
):
    backend.update = AsyncMock(side_effect=CancelledError())
    monkeypatch.setattr(trace_service, 'db_update', backend.update)
    with pytest.raises(CancelledError):
        await trace_service._recompress(TraceId(1), _ORIGINAL, _DATA)
    assert backend.current == _ORIGINAL
    assert set(backend.files) == {_ORIGINAL}


async def test_delete_locks_current_file_until_row_deletion(backend):
    await trace_service.TraceService.delete(TraceId(1))
    assert backend.current is None
    assert _ORIGINAL not in backend.files


@pytest.mark.parametrize('first', ['replace', 'delete'])
async def test_delete_and_recompression_interleavings_remove_all_files(
    backend, monkeypatch, first
):
    entered, release = Event(), Event()
    operation = backend.update if first == 'replace' else backend.fetchval

    async def pause_in_transaction(*args, **kwargs):
        result = await operation(*args, **kwargs)
        entered.set()
        await release.wait()
        return result

    monkeypatch.setattr(
        trace_service,
        'db_update' if first == 'replace' else 'db_fetchval',
        pause_in_transaction,
    )
    replacing = lambda: trace_service._recompress(TraceId(1), _ORIGINAL, _DATA)
    deleting = lambda: trace_service.TraceService.delete(TraceId(1))
    first_task = create_task(replacing() if first == 'replace' else deleting())
    second_task = None
    try:
        await wait_for(entered.wait(), 2)
        second_task = create_task(deleting() if first == 'replace' else replacing())
        await sleep(0)
        assert not second_task.done()
    finally:
        release.set()
        await wait_for(gather(first_task, *([second_task] if second_task else [])), 2)
    assert backend.current is None
    assert not backend.files


async def test_download_retries_changed_key(backend, monkeypatch):
    backend.files[_REPLACEMENT] = zstd.compress(_DATA)
    backend.files.pop(_ORIGINAL)
    get_by_id = AsyncMock(
        side_effect=[{'file_id': _ORIGINAL}, {'file_id': _REPLACEMENT}]
    )
    monkeypatch.setattr(trace_query.TraceQuery, 'get_by_id', get_by_id)
    assert await trace_query.TraceQuery.get_one_data_by_id(TraceId(1)) == _DATA
    assert get_by_id.await_count == 2
    assert [event for event in backend.events if isinstance(event, tuple)] == [
        ('load', _ORIGINAL),
        ('load', _REPLACEMENT),
    ]


async def test_download_preserves_unchanged_key_failure(backend, monkeypatch):
    backend.files.clear()
    get_by_id = AsyncMock(return_value={'file_id': _ORIGINAL})
    monkeypatch.setattr(trace_query.TraceQuery, 'get_by_id', get_by_id)
    with pytest.raises(KeyError):
        await trace_query.TraceQuery.get_one_data_by_id(TraceId(1))
    assert backend.events.count(('load', _ORIGINAL)) == 1


async def test_download_rechecks_access_before_retry(backend, monkeypatch):
    backend.files.clear()
    get_by_id = AsyncMock(
        side_effect=[{'file_id': _ORIGINAL}, PermissionError('private')]
    )
    monkeypatch.setattr(trace_query.TraceQuery, 'get_by_id', get_by_id)
    with pytest.raises(PermissionError):
        await trace_query.TraceQuery.get_one_data_by_id(TraceId(1))
    assert backend.events == [('load', _ORIGINAL)]


async def test_upload_returns_before_recompression_and_drains_at_exit(
    backend, monkeypatch
):
    backend.current = None
    backend.next_id = _ORIGINAL
    previous_tasks = trace_service._RECOMPRESS_TASKS
    request = ContextVar('test_trace_request', default=None)
    started, finish = Event(), Event()
    observations = []

    async def recompress(trace_id, original_id, file):
        observations.append((backend.current, request.get(), file))
        started.set()
        await finish.wait()

    monkeypatch.setattr(trace_service, '_recompress', recompress)
    monkeypatch.setattr(TraceFile, 'extract', lambda data: [data])
    monkeypatch.setattr(trace_service.XMLToDict, 'parse', lambda _data: {})
    monkeypatch.setattr(
        trace_service.FormatGPX,
        'decode_tracks',
        lambda _tracks: SimpleNamespace(
            size=1,
            segments=SimpleNamespace(geoms=[]),
            elevations=None,
            capture_times=None,
        ),
    )
    monkeypatch.setattr(
        trace_service.TraceInitValidator, 'validate_python', lambda data: data
    )
    request.set('private request state')
    exiting, exited = Event(), Event()

    async def upload_and_exit():
        async with trace_service.TraceService.context():
            trace_id = await wait_for(
                trace_service.TraceService.upload(
                    _DATA,
                    name='trace.gpx',
                    description='',
                    tags=[],
                    visibility='public',
                ),
                2,
            )
            assert trace_id == 1
            await wait_for(started.wait(), 2)
            assert observations == [(_ORIGINAL, None, _DATA)]
            exiting.set()
        exited.set()

    task = create_task(upload_and_exit())
    try:
        await wait_for(exiting.wait(), 2)
        await sleep(0)
        assert not exited.is_set()
    finally:
        finish.set()
        await wait_for(task, 2)
    assert trace_service._RECOMPRESS_TASKS is previous_tasks


async def test_upload_recompresses_original_bytes_end_to_end(backend, monkeypatch):
    backend.current = None
    backend.next_id = _ORIGINAL
    monkeypatch.setattr(TraceFile, 'extract', lambda data: [data])
    monkeypatch.setattr(trace_service.XMLToDict, 'parse', lambda _data: {})
    monkeypatch.setattr(
        trace_service.FormatGPX,
        'decode_tracks',
        lambda _tracks: SimpleNamespace(
            size=1,
            segments=SimpleNamespace(geoms=[]),
            elevations=None,
            capture_times=None,
        ),
    )
    monkeypatch.setattr(
        trace_service.TraceInitValidator, 'validate_python', lambda data: data
    )

    @asynccontextmanager
    async def original_context():
        yield

    context = getattr(trace_service.TraceService, 'context', original_context)
    async with context():
        assert (
            await trace_service.TraceService.upload(
                _DATA, name='trace.gpx', description='', tags=[], visibility='public'
            )
            == 1
        )
    assert backend.current == _REPLACEMENT
    assert backend.metadata[_REPLACEMENT] == {'zstd_level': '22'}
    assert zstd.decompress(backend.files[_REPLACEMENT]) == _DATA
    assert _ORIGINAL not in backend.files


async def test_upload_does_not_fail_after_commit_if_scheduler_rejects(
    backend, monkeypatch
):
    backend.current = None
    backend.next_id = _ORIGINAL
    monkeypatch.setattr(TraceFile, 'extract', lambda data: [data])
    monkeypatch.setattr(trace_service.XMLToDict, 'parse', lambda _data: {})
    monkeypatch.setattr(
        trace_service.FormatGPX,
        'decode_tracks',
        lambda _tracks: SimpleNamespace(
            size=1,
            segments=SimpleNamespace(geoms=[]),
            elevations=None,
            capture_times=None,
        ),
    )
    monkeypatch.setattr(
        trace_service.TraceInitValidator, 'validate_python', lambda data: data
    )

    class _ClosedGroup:
        def create_task(self, coroutine, **kwargs):
            raise RuntimeError('group closed')

    monkeypatch.setattr(trace_service, '_RECOMPRESS_TASKS', _ClosedGroup())
    assert (
        await trace_service.TraceService.upload(
            _DATA, name='trace.gpx', description='', tags=[], visibility='public'
        )
        == 1
    )
    assert backend.current == _ORIGINAL and _ORIGINAL in backend.files
