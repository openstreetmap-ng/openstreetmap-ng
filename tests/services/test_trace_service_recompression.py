from types import SimpleNamespace

import app.services.trace_service as trace_service
from app.config import TRACE_FILE_RECOMPRESS_ZSTD_LEVEL
from app.models.types import StorageKey, TraceId


class _Storage:
    def __init__(self):
        self.saved: list[tuple[bytes, str, dict[str, str]]] = []
        self.deleted: list[StorageKey] = []

    async def save(self, data: bytes, suffix: str, metadata: dict[str, str]):
        self.saved.append((data, suffix, metadata))
        return StorageKey(f'new{suffix}')

    async def delete(self, key: StorageKey):
        self.deleted.append(key)


async def test_recompress_trace_file_swaps_current_file(monkeypatch):
    storage = _Storage()
    updates = []

    async def compress(file: bytes, *, level: int):
        assert file == b'<gpx />'
        assert level == TRACE_FILE_RECOMPRESS_ZSTD_LEVEL
        return SimpleNamespace(
            data=b'heavily-compressed',
            suffix='.zst',
            metadata={'zstd_level': str(level)},
        )

    async def db_update(table: str, values: dict, *, where: dict):
        updates.append((table, values, where))
        return 1

    monkeypatch.setattr(trace_service.TraceFile, 'compress', compress)
    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_service, 'db_update', db_update)

    await trace_service._recompress_trace_file(
        TraceId(123), b'<gpx />', StorageKey('old.zst')
    )

    assert storage.saved == [
        (b'heavily-compressed', '.zst', {'zstd_level': '22'})
    ]
    assert updates == [
        (
            'trace',
            {'file_id': StorageKey('new.zst')},
            {'id': TraceId(123), 'file_id': StorageKey('old.zst')},
        )
    ]
    assert storage.deleted == [StorageKey('old.zst')]


async def test_recompress_trace_file_deletes_new_file_when_trace_changed(monkeypatch):
    storage = _Storage()

    async def compress(file: bytes, *, level: int):
        return SimpleNamespace(
            data=b'heavily-compressed',
            suffix='.zst',
            metadata={'zstd_level': str(level)},
        )

    async def db_update(table: str, values: dict, *, where: dict):
        return 0

    monkeypatch.setattr(trace_service.TraceFile, 'compress', compress)
    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_service, 'db_update', db_update)

    await trace_service._recompress_trace_file(
        TraceId(123), b'<gpx />', StorageKey('old.zst')
    )

    assert storage.deleted == [StorageKey('new.zst')]
