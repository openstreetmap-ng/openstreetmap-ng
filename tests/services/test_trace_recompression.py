# ruff: noqa: SLF001
import asyncio
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from botocore.exceptions import ClientError
from psycopg import sql

from app.lib.io.trace_file import TraceFile
from app.queries import trace_query as query
from app.services import trace_service as service

DSN = os.getenv('OSM_TRACE_TEST_DSN')
pytestmark = pytest.mark.skipif(
    not DSN, reason='Set OSM_TRACE_TEST_DSN to an isolated PostgreSQL test database'
)
DATA = (
    b'<gpx>'
    + b''.join(f'<trkpt lat="{i % 7}" lon="{i % 19}"/>'.encode() for i in range(100))
    + b'</gpx>'
)


@pytest.fixture
async def trace_env(monkeypatch):
    schema = 'trace_recompression_' + uuid4().hex
    async with await psycopg.AsyncConnection.connect(DSN, autocommit=True) as conn:
        await conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        await conn.execute(
            sql.SQL(
                'CREATE TABLE {}.trace (id bigint PRIMARY KEY, user_id bigint NOT NULL, file_id text NOT NULL)'
            ).format(sql.Identifier(schema))
        )
    state = SimpleNamespace(
        files={},
        metadata={},
        errors=[],
        fail_update=False,
        lose_commit=False,
        counter=0,
    )

    @asynccontextmanager
    async def database(write=False):
        async with await psycopg.AsyncConnection.connect(DSN) as conn:
            await conn.execute(
                sql.SQL('SET search_path TO {}').format(sql.Identifier(schema))
            )
            yield conn
        if state.lose_commit:
            state.lose_commit = False
            raise OSError('lost commit acknowledgement')

    async def fetchval(type_, query, *, conn=None):
        if conn is None:
            async with database() as conn:
                return await fetchval(type_, query, conn=conn)
        cursor = await conn.execute('%s'.join(query.strings), query.values)
        row = await cursor.fetchone()
        return row[0] if row else None

    async def update(table, values, *, where, conn):
        if state.fail_update:
            raise OSError('update failed')
        cursor = await conn.execute(
            'UPDATE trace SET file_id = %s WHERE id = %s AND file_id = %s',
            (values['file_id'], where['id'], where['file_id']),
        )
        return cursor.rowcount

    async def delete(table, *, where, conn):
        cursor = await conn.execute(
            'DELETE FROM trace WHERE id = %s AND user_id = %s',
            (where['id'], where['user_id']),
        )
        return cursor.rowcount

    async def insert(table, values, *, returning, conn):
        await conn.execute(
            'INSERT INTO trace VALUES (1, %s, %s)',
            (values['user_id'], values['file_id']),
        )
        return (1,)

    async def save(data, suffix, metadata):
        state.counter += 1
        key = f'file-{state.counter}{suffix}'
        state.files[key] = data
        state.metadata[key] = metadata
        return key

    async def remove(key):
        state.files.pop(key, None)
        state.metadata.pop(key, None)

    async def audit(*args, **kwargs):
        pass

    monkeypatch.setattr(service, 'db', database)
    monkeypatch.setattr(service, 'db_fetchval', fetchval)
    monkeypatch.setattr(service, 'db_update', update)
    monkeypatch.setattr(service, 'db_delete', delete)
    monkeypatch.setattr(service, 'db_insert', insert)
    monkeypatch.setattr(
        service, 'TRACE_STORAGE', SimpleNamespace(save=save, delete=remove)
    )
    monkeypatch.setattr(service, 'auth_user', lambda **_kwargs: {'id': 1})
    monkeypatch.setattr(service, 'audit', audit)
    monkeypatch.setattr(service, 'capture_exception', state.errors.append)

    async def fetchone(type_, template):
        async with database() as conn:
            cursor = await conn.execute('%s'.join(template.strings), template.values)
            row = await cursor.fetchone()
            return (
                dict(
                    zip(
                        (column.name for column in cursor.description), row, strict=True
                    )
                )
                if row
                else None
            )

    monkeypatch.setattr(query, 'db_fetchone', fetchone)
    monkeypatch.setattr(query, 'trace_is_visible', lambda _trace: True)
    monkeypatch.setattr(query, 'TRACE_STORAGE', service.TRACE_STORAGE)
    state.db, state.update, state.fetchval = database, update, fetchval
    state.save = save

    async def prepare(data=DATA):
        original = await TraceFile.compress(data)
        key = await save(original.data, original.suffix, original.metadata)
        async with database(True) as conn:
            await conn.execute('INSERT INTO trace VALUES (1, 1, %s)', (key,))
        return key, len(original.data)

    async def current():
        return await fetchval(str, t'SELECT file_id FROM trace WHERE id = {1}')

    state.prepare, state.current = prepare, current
    try:
        yield state
    finally:
        if service._RECOMPRESS_TASKS:
            await asyncio.gather(*service._RECOMPRESS_TASKS)
        async with await psycopg.AsyncConnection.connect(DSN, autocommit=True) as conn:
            await conn.execute(
                sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema))
            )


async def test_recompression_replaces_file_after_commit(trace_env):
    state = trace_env
    old, size = await state.prepare()
    await service._recompress_trace(1, old, DATA, size)
    current = await state.current()
    assert current != old
    assert set(state.files) == {current}
    assert state.metadata[current] == {'zstd_level': '22'}
    assert TraceFile.decompress_if_needed(state.files[current], current) == DATA
    assert not state.errors


async def test_non_improving_compression_keeps_original(trace_env):
    state = trace_env
    old, size = await state.prepare(b'hello')
    await service._recompress_trace(1, old, b'hello', size)
    assert await state.current() == old
    assert set(state.files) == {old}


async def test_deleted_trace_discards_recompressed_file(trace_env, monkeypatch):
    state = trace_env
    old, size = await state.prepare()

    async def save_then_delete(*args):
        key = await state.save(*args)
        await service.TraceService.delete(1)
        return key

    monkeypatch.setattr(service.TRACE_STORAGE, 'save', save_then_delete)
    await service._recompress_trace(1, old, DATA, size)
    assert await state.current() is None
    assert not state.files


@pytest.mark.parametrize('delete_first', [True, False])
async def test_delete_and_recompression_serialize_file_ownership(
    trace_env, monkeypatch, delete_first
):
    state = trace_env
    old, size = await state.prepare()
    locked, release = asyncio.Event(), asyncio.Event()
    if delete_first:

        async def locked_read(type_, query, *, conn=None):
            result = await state.fetchval(type_, query, conn=conn)
            if conn is not None:
                locked.set()
                await release.wait()
            return result

        monkeypatch.setattr(service, 'db_fetchval', locked_read)
        first = asyncio.create_task(service.TraceService.delete(1))
    else:

        async def locked_update(*args, **kwargs):
            result = await state.update(*args, **kwargs)
            locked.set()
            await release.wait()
            return result

        monkeypatch.setattr(service, 'db_update', locked_update)
        first = asyncio.create_task(service._recompress_trace(1, old, DATA, size))
    await asyncio.wait_for(locked.wait(), 2)
    second = asyncio.create_task(
        service._recompress_trace(1, old, DATA, size)
        if delete_first
        else service.TraceService.delete(1)
    )
    try:
        await asyncio.sleep(0.05)
        assert not second.done()
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(first, second), 10)
    assert await state.current() is None
    assert not state.files


async def test_update_failure_preserves_old_file_and_cleans_candidate(trace_env):
    state = trace_env
    old, size = await state.prepare()
    state.fail_update = True
    await service._recompress_trace(1, old, DATA, size)
    assert await state.current() == old
    assert set(state.files) == {old}
    assert len(state.errors) == 1


async def test_lost_commit_acknowledgement_never_deletes_active_file(trace_env):
    state = trace_env
    old, size = await state.prepare()
    state.lose_commit = True
    await service._recompress_trace(1, old, DATA, size)
    current = await state.current()
    assert current != old
    assert set(state.files) == {current}
    assert TraceFile.decompress_if_needed(state.files[current], current) == DATA
    assert len(state.errors) == 1


async def test_upload_returns_after_commit_without_waiting_for_recompression(
    trace_env, monkeypatch
):
    state = trace_env
    started, release = asyncio.Event(), asyncio.Event()

    async def recompress(trace_id, file_id, data, size):
        assert await state.current() == file_id
        started.set()
        await release.wait()

    monkeypatch.setattr(service, '_recompress_trace', recompress)
    monkeypatch.setattr(service.TraceFile, 'extract', lambda _data: [])
    monkeypatch.setattr(
        service.FormatGPX,
        'decode_tracks',
        lambda _tracks: SimpleNamespace(
            size=1,
            segments=SimpleNamespace(geoms=[1]),
            elevations=None,
            capture_times=None,
        ),
    )
    monkeypatch.setattr(
        service.TraceInitValidator, 'validate_python', lambda value: value
    )
    trace_id = await asyncio.wait_for(
        service.TraceService.upload(
            DATA, name='test.gpx', description='', tags=[], visibility=0
        ),
        2,
    )
    assert trace_id == 1
    await asyncio.wait_for(started.wait(), 2)
    assert len(service._RECOMPRESS_TASKS) == 1
    release.set()
    await asyncio.gather(*service._RECOMPRESS_TASKS)
    await asyncio.sleep(0)
    assert not service._RECOMPRESS_TASKS


@pytest.mark.parametrize('failure', ['compress', 'save'])
async def test_recompression_failure_preserves_original(
    trace_env, monkeypatch, failure
):
    state = trace_env
    old, size = await state.prepare()

    async def fail(*args, **kwargs):
        raise OSError('injected failure')

    if failure == 'compress':
        monkeypatch.setattr(service.TraceFile, 'compress', fail)
    else:
        monkeypatch.setattr(service.TRACE_STORAGE, 'save', fail)
    await service._recompress_trace(1, old, DATA, size)
    assert await state.current() == old
    assert set(state.files) == {old}
    assert len(state.errors) == 1


async def test_cancelled_update_rolls_back_and_cleans_candidate(trace_env, monkeypatch):
    state = trace_env
    old, size = await state.prepare()
    updating = asyncio.Event()

    async def wait_for_cancel(*args, **kwargs):
        updating.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(service, 'db_update', wait_for_cancel)
    task = asyncio.create_task(service._recompress_trace(1, old, DATA, size))
    await asyncio.wait_for(updating.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await state.current() == old
    assert set(state.files) == {old}
    assert not state.errors


async def test_changed_file_is_not_overwritten(trace_env, monkeypatch):
    state = trace_env
    old, size = await state.prepare()

    async def save_then_replace(*args):
        candidate = await state.save(*args)
        state.files['replacement.zst'] = state.files.pop(old)
        async with state.db(True) as conn:
            await conn.execute(
                'UPDATE trace SET file_id = %s WHERE id = 1', ('replacement.zst',)
            )
        return candidate

    monkeypatch.setattr(service.TRACE_STORAGE, 'save', save_then_replace)
    await service._recompress_trace(1, old, DATA, size)
    assert await state.current() == 'replacement.zst'
    assert set(state.files) == {'replacement.zst'}


@pytest.mark.parametrize('storage_kind', ['db', 's3'])
async def test_download_retries_replaced_file(trace_env, monkeypatch, storage_kind):
    state = trace_env
    old, size = await state.prepare()
    loads = []

    async def load(key):
        loads.append(key)
        if key == old:
            await service._recompress_trace(1, old, DATA, size)
            if storage_kind == 'db':
                raise FileNotFoundError(key)
            raise ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
        return state.files[key]

    monkeypatch.setattr(service.TRACE_STORAGE, 'load', load, raising=False)
    assert await query.TraceQuery.get_one_data_by_id(1) == DATA
    assert loads == [old, await state.current()]


@pytest.mark.parametrize(
    'error',
    [
        FileNotFoundError('unchanged file'),
        ClientError({'Error': {'Code': 'AccessDenied'}}, 'GetObject'),
    ],
)
async def test_download_does_not_hide_unrelated_storage_errors(
    trace_env, monkeypatch, error
):
    state = trace_env
    await state.prepare()
    loads = []

    async def load(key):
        loads.append(key)
        raise error

    monkeypatch.setattr(service.TRACE_STORAGE, 'load', load, raising=False)
    with pytest.raises(type(error)):
        await query.TraceQuery.get_one_data_by_id(1)
    assert len(loads) == 1


async def test_service_shutdown_joins_cancellation_cleanup(trace_env, monkeypatch):
    state = trace_env
    old, size = await state.prepare()
    updating = asyncio.Event()

    async def wait_for_cancel(*args, **kwargs):
        updating.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(service, 'db_update', wait_for_cancel)
    async with service.TraceService.context():
        task = asyncio.create_task(service._recompress_trace(1, old, DATA, size))
        service._RECOMPRESS_TASKS.add(task)
        task.add_done_callback(service._RECOMPRESS_TASKS.discard)
        await asyncio.wait_for(updating.wait(), 2)
    assert task.cancelled()
    assert not service._RECOMPRESS_TASKS
    assert await state.current() == old
    assert set(state.files) == {old}
