from types import SimpleNamespace
from typing import LiteralString

from app.models.types import StorageKey, TraceId
from app.services import trace_service


class _FakeStorage:
    def __init__(self):
        self.saved: list[tuple[bytes, LiteralString, dict[str, str] | None]] = []
        self.deleted: list[StorageKey] = []

    async def save(
        self, data: bytes, suffix: LiteralString, metadata: dict[str, str] | None = None
    ):
        self.saved.append((data, suffix, metadata))
        return StorageKey(f'new-{len(self.saved)}{suffix}')

    async def delete(self, key: StorageKey):
        self.deleted.append(key)


async def test_recompress_trace_file_replaces_current_storage(monkeypatch):
    storage = _FakeStorage()
    updates = []

    async def fake_compress(buffer: bytes, *, level: int):
        return SimpleNamespace(
            data=b'heavy:' + buffer,
            suffix='.zst',
            metadata={'zstd_level': str(level)},
        )

    async def fake_db_update(table, values, *, where):
        updates.append((table, values, where))
        return 1

    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_service.TraceFile, 'compress', fake_compress)
    monkeypatch.setattr(trace_service, 'db_update', fake_db_update)

    await trace_service._recompress_trace_file(  # noqa: SLF001
        TraceId(123),
        StorageKey('old.zst'),
        b'gpx-bytes',
    )

    assert storage.saved == [
        (b'heavy:gpx-bytes', '.zst', {'zstd_level': '22'}),
    ]
    assert updates == [
        (
            'trace',
            {'file_id': StorageKey('new-1.zst')},
            {'id': TraceId(123), 'file_id': StorageKey('old.zst')},
        ),
    ]
    assert storage.deleted == [StorageKey('old.zst')]


async def test_recompress_trace_file_discards_new_file_when_trace_changed(monkeypatch):
    storage = _FakeStorage()

    async def fake_compress(buffer: bytes, *, level: int):
        return SimpleNamespace(
            data=b'heavy:' + buffer,
            suffix='.zst',
            metadata={'zstd_level': str(level)},
        )

    async def fake_db_update(table, values, *, where):
        return 0

    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_service.TraceFile, 'compress', fake_compress)
    monkeypatch.setattr(trace_service, 'db_update', fake_db_update)

    await trace_service._recompress_trace_file(  # noqa: SLF001
        TraceId(123),
        StorageKey('old.zst'),
        b'gpx-bytes',
    )

    assert storage.deleted == [StorageKey('new-1.zst')]
