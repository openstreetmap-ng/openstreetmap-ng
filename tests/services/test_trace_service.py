from contextlib import asynccontextmanager
from types import SimpleNamespace

from app.models.types import StorageKey, TraceId
from app.services import trace_service


async def test_delete_removes_file_from_deleted_trace(monkeypatch):
    deleted: list[StorageKey] = []

    @asynccontextmanager
    async def db(*_):
        yield object()

    async def db_delete(table: str, **kwargs):
        assert table == 'trace'
        assert kwargs['where'] == {'id': TraceId(1), 'user_id': 2}
        assert kwargs['returning'] == 'file_id'
        assert kwargs['assert_returning'] is False
        return (StorageKey('recompressed.zst'),)

    async def unexpected_db_fetchval(*_, **__):
        raise AssertionError('successful delete must not prefetch file_id')

    async def audit(*_, **__):
        pass

    async def delete(key: StorageKey):
        deleted.append(key)

    monkeypatch.setattr(trace_service, 'auth_user', lambda **_: {'id': 2})
    monkeypatch.setattr(trace_service, 'db', db)
    monkeypatch.setattr(trace_service, 'db_delete', db_delete)
    monkeypatch.setattr(trace_service, 'db_fetchval', unexpected_db_fetchval)
    monkeypatch.setattr(trace_service, 'audit', audit)
    monkeypatch.setattr(
        trace_service,
        'TRACE_STORAGE',
        SimpleNamespace(delete=delete),
    )

    await trace_service.TraceService.delete(TraceId(1))

    assert deleted == [StorageKey('recompressed.zst')]


async def test_recompress_context_drains_queued_trace(monkeypatch):
    calls: list[tuple[TraceId, StorageKey, bytes]] = []

    async def recompress_task(
        trace_id: TraceId,
        old_file_id: StorageKey,
        file_bytes: bytes,
    ):
        calls.append((trace_id, old_file_id, file_bytes))

    monkeypatch.setattr(trace_service, '_recompress_task', recompress_task)

    async with trace_service.TraceService.context():
        trace_service._RECOMPRESS_QUEUE.put_nowait(  # noqa: SLF001
            (TraceId(1), StorageKey('old.zst'), b'original')
        )

    assert calls == [(TraceId(1), StorageKey('old.zst'), b'original')]


async def test_recompress_task_replaces_trace_file(monkeypatch):
    saved: list[tuple[bytes, str, dict[str, str]]] = []
    deleted: list[StorageKey] = []
    updates: list[tuple[str, dict[str, StorageKey], dict[str, object]]] = []

    async def recompress(_: bytes):
        return SimpleNamespace(
            data=b'recompressed',
            suffix='.zst',
            metadata={'zstd_level': '22'},
        )

    async def save(data: bytes, suffix: str, metadata: dict[str, str]):
        saved.append((data, suffix, metadata))
        return StorageKey('new.zst')

    async def delete(key: StorageKey):
        deleted.append(key)

    async def db_update(table: str, values: dict, *, where: dict):
        updates.append((table, values, where))
        return 1

    monkeypatch.setattr(trace_service.TraceFile, 'recompress', recompress)
    monkeypatch.setattr(
        trace_service,
        'TRACE_STORAGE',
        SimpleNamespace(save=save, delete=delete),
    )
    monkeypatch.setattr(trace_service, 'db_update', db_update)

    await trace_service._recompress_task(  # noqa: SLF001
        TraceId(1),
        StorageKey('old.zst'),
        b'original',
    )

    assert saved == [(b'recompressed', '.zst', {'zstd_level': '22'})]
    assert updates == [
        (
            'trace',
            {'file_id': StorageKey('new.zst')},
            {'id': TraceId(1), 'file_id': StorageKey('old.zst')},
        )
    ]
    assert deleted == [StorageKey('old.zst')]


async def test_recompress_task_discards_unclaimed_file(monkeypatch):
    deleted: list[StorageKey] = []

    async def recompress(_: bytes):
        return SimpleNamespace(data=b'recompressed', suffix='.zst', metadata={})

    async def save(*_):
        return StorageKey('new.zst')

    async def delete(key: StorageKey):
        deleted.append(key)

    async def db_update(*_, **__):
        return 0

    monkeypatch.setattr(trace_service.TraceFile, 'recompress', recompress)
    monkeypatch.setattr(
        trace_service,
        'TRACE_STORAGE',
        SimpleNamespace(save=save, delete=delete),
    )
    monkeypatch.setattr(trace_service, 'db_update', db_update)

    await trace_service._recompress_task(  # noqa: SLF001
        TraceId(1),
        StorageKey('old.zst'),
        b'original',
    )

    assert deleted == [StorageKey('new.zst')]


async def test_recompress_task_tolerates_old_file_cleanup_failure(monkeypatch):
    captured: list[None] = []

    async def recompress(_: bytes):
        return SimpleNamespace(data=b'recompressed', suffix='.zst', metadata={})

    async def save(*_):
        return StorageKey('new.zst')

    async def delete(key: StorageKey):
        assert key == StorageKey('old.zst')
        raise RuntimeError('storage cleanup unavailable')

    async def db_update(*_, **__):
        return 1

    monkeypatch.setattr(trace_service.TraceFile, 'recompress', recompress)
    monkeypatch.setattr(
        trace_service,
        'TRACE_STORAGE',
        SimpleNamespace(save=save, delete=delete),
    )
    monkeypatch.setattr(trace_service, 'db_update', db_update)
    monkeypatch.setattr(trace_service, 'capture_exception', lambda: captured.append(None))

    await trace_service._recompress_task(  # noqa: SLF001
        TraceId(1),
        StorageKey('old.zst'),
        b'original',
    )

    assert captured == [None]
