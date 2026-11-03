# ruff: noqa: SLF001

from asyncio import Event, sleep
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.db import db_fetchval
from app.lib.io.trace_file import TraceFile
from app.lib.storage import TRACE_STORAGE
from app.models.types import StorageKey
from app.services import trace_recompression_service as module
from app.services.trace_recompression_service import TraceRecompressionService

_GPX = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<gpx version="1.1" creator="tests"><trk><trkseg>'
    b'<trkpt lat="10" lon="20"/><trkpt lat="11" lon="21"/>'
    b'</trkseg></trk><!--' + b'recompression regression ' * 1000 + b'--></gpx>'
)


@pytest.fixture(autouse=True)
async def drained_worker():
    await TraceRecompressionService.drain()
    yield
    await TraceRecompressionService.drain()


async def _upload(client, monkeypatch):
    # Store a legacy uncompressed file to deterministically exercise replacement.
    async def uncompressed(buffer):
        return SimpleNamespace(data=buffer, suffix='.gpx', metadata={})

    with monkeypatch.context() as patch:
        patch.setattr(TraceFile, 'compress', uncompressed)
        patch.setattr(TraceRecompressionService, 'schedule', lambda *_: None)
        client.headers['Authorization'] = 'User user1'
        response = await client.post(
            '/api/0.6/gpx/create',
            data={'visibility': 'public', 'description': 'Recompression regression'},
            files={'file': ('compression.gpx', _GPX)},
        )
    assert response.is_success, response.text
    trace_id = int(response.text)
    file_id = await _key(trace_id)
    assert file_id is not None
    return trace_id, file_id


async def _key(trace_id):
    return await db_fetchval(
        StorageKey, t'SELECT file_id FROM trace WHERE id = {trace_id}'
    )


async def test_recompress_round_trip(client: AsyncClient, monkeypatch):
    trace_id, old_key = await _upload(client, monkeypatch)
    await module._recompress(trace_id, old_key)
    new_key = await _key(trace_id)
    assert new_key is not None and new_key != old_key
    stored = await TRACE_STORAGE.load(new_key)
    assert len(stored) < len(_GPX)
    assert TraceFile.decompress_if_needed(stored, new_key) == _GPX
    with pytest.raises(FileNotFoundError):
        await TRACE_STORAGE.load(old_key)
    # Repeated/stale jobs are harmless.
    await module._recompress(trace_id, old_key)
    assert await TRACE_STORAGE.load(new_key) == stored


@pytest.mark.parametrize('commit_succeeded', [True, False])
async def test_uncertain_commit_preserves_live_file(
    client: AsyncClient, monkeypatch, commit_succeeded
):
    trace_id, old_key = await _upload(client, monkeypatch)
    real_db = module.db

    @asynccontextmanager
    async def broken_ack(*args, **kwargs):
        async with real_db(*args, **kwargs) as conn:
            yield conn
            if not commit_succeeded:
                raise ConnectionError('rollback before commit')
        raise ConnectionError('lost commit acknowledgement')

    monkeypatch.setattr(module, 'db', broken_ack)
    with pytest.raises(ConnectionError):
        await module._recompress(trace_id, old_key)
    live_key = await _key(trace_id)
    assert live_key is not None
    assert (live_key != old_key) == commit_succeeded
    data = await TRACE_STORAGE.load(live_key)
    assert TraceFile.decompress_if_needed(data, live_key) == _GPX


async def test_database_outage_retains_both_objects(client: AsyncClient, monkeypatch):
    trace_id, old_key = await _upload(client, monkeypatch)
    new_key = await TRACE_STORAGE.save(b'replacement', '.zst')

    async def unavailable(*args, **kwargs):
        raise ConnectionError('database unavailable')

    monkeypatch.setattr(module, 'db_fetchval', unavailable)
    await module._cleanup(trace_id, old_key, new_key)
    assert await TRACE_STORAGE.load(old_key) == _GPX
    assert await TRACE_STORAGE.load(new_key) == b'replacement'
    await TRACE_STORAGE.delete(new_key)


async def test_deleted_trace_does_not_get_resurrected(client: AsyncClient, monkeypatch):
    trace_id, old_key = await _upload(client, monkeypatch)
    real_compress = TraceFile.compress

    async def delete_during_compression(buffer, **kwargs):
        response = await client.delete(f'/api/0.6/gpx/{trace_id}')
        assert response.is_success, response.text
        return await real_compress(buffer, **kwargs)

    monkeypatch.setattr(TraceFile, 'compress', delete_during_compression)
    await module._recompress(trace_id, old_key)
    assert await _key(trace_id) is None
    with pytest.raises(FileNotFoundError):
        await TRACE_STORAGE.load(old_key)


async def test_not_smaller_keeps_original(client: AsyncClient, monkeypatch):
    trace_id, old_key = await _upload(client, monkeypatch)

    async def larger(buffer, **kwargs):
        return SimpleNamespace(data=buffer + b'x', suffix='.zst', metadata={})

    monkeypatch.setattr(TraceFile, 'compress', larger)
    await module._recompress(trace_id, old_key)
    assert await _key(trace_id) == old_key
    assert await TRACE_STORAGE.load(old_key) == _GPX


async def test_upload_returns_while_worker_waits(client: AsyncClient, monkeypatch):
    entered, release = Event(), Event()

    async def paused(*args):
        entered.set()
        await release.wait()

    monkeypatch.setattr(module, '_recompress', paused)
    client.headers['Authorization'] = 'User user1'
    response = await client.post(
        '/api/0.6/gpx/create',
        data={'visibility': 'public', 'description': 'Nonblocking compression'},
        files={'file': ('background.gpx', _GPX)},
    )
    try:
        assert response.is_success, response.text
        # Give the independent worker a chance to consume the queued ID.
        for _ in range(100):
            if entered.is_set():
                break
            await sleep(0)
        assert entered.is_set()
    finally:
        release.set()
        await TraceRecompressionService.drain()


async def test_download_retries_retired_pointer(client: AsyncClient, monkeypatch):
    trace_id, old_key = await _upload(client, monkeypatch)
    real_load = TRACE_STORAGE.load
    retired = False

    async def racing_load(self, key):
        nonlocal retired
        if key == old_key and not retired:
            retired = True
            await module._recompress(trace_id, old_key)
            raise FileNotFoundError(key)
        return await real_load(key)

    # Storage instances use slots; patch the class while retaining the real bound method.
    monkeypatch.setattr(type(TRACE_STORAGE), 'load', racing_load)
    response = await client.get(f'/api/0.6/gpx/{trace_id}/data')
    assert response.is_success, response.text
    assert response.content == _GPX


async def test_level_metadata():
    for level in (6, 22):
        result = await TraceFile.compress(_GPX, level=level)
        assert result.metadata == {'zstd_level': str(level)}
        assert (
            TraceFile.decompress_if_needed(result.data, StorageKey('test.zst')) == _GPX
        )
