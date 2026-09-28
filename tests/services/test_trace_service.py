# ruff: noqa: SLF001

from types import SimpleNamespace

from app.models.types import StorageKey, TraceId
from app.services import trace_service


class _FakeStorage:
    def __init__(self):
        self.saved: list[tuple[bytes, str, dict[str, str]]] = []
        self.deleted: list[StorageKey] = []

    async def save(self, data: bytes, suffix: str, metadata: dict[str, str]):
        self.saved.append((data, suffix, metadata))
        return StorageKey(f'recompressed-{len(self.saved)}{suffix}')

    async def delete(self, key: StorageKey):
        self.deleted.append(key)


class _FakeDB:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount
        self.params: tuple | None = None

    def __call__(self, _write: bool):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def execute(self, _query: str, params: tuple):
        self.params = params
        return SimpleNamespace(rowcount=self.rowcount)


async def test_recompress_trace_file_swaps_current_file(monkeypatch):
    storage = _FakeStorage()
    db = _FakeDB(rowcount=1)

    async def compress(_file: bytes, *, level: int):
        return SimpleNamespace(
            data=b'small',
            suffix='.zst',
            metadata={'zstd_level': str(level)},
        )

    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_service, 'db', db)
    monkeypatch.setattr(trace_service.TraceFile, 'compress', compress)

    await trace_service._recompress_trace_file(
        TraceId(123), StorageKey('old.zst'), b'content', compressed_size=100
    )

    assert storage.saved == [(b'small', '.zst', {'zstd_level': '22'})]
    assert storage.deleted == [StorageKey('old.zst')]
    assert db.params == (
        StorageKey('recompressed-1.zst'),
        TraceId(123),
        StorageKey('old.zst'),
    )


async def test_recompress_trace_file_deletes_new_file_when_trace_changes(monkeypatch):
    storage = _FakeStorage()

    async def compress(_file: bytes, *, level: int):
        return SimpleNamespace(
            data=b'small',
            suffix='.zst',
            metadata={'zstd_level': str(level)},
        )

    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_service, 'db', _FakeDB(rowcount=0))
    monkeypatch.setattr(trace_service.TraceFile, 'compress', compress)

    await trace_service._recompress_trace_file(
        TraceId(123), StorageKey('old.zst'), b'content', compressed_size=100
    )

    assert storage.saved == [(b'small', '.zst', {'zstd_level': '22'})]
    assert storage.deleted == [StorageKey('recompressed-1.zst')]


async def test_recompress_trace_file_skips_larger_result(monkeypatch):
    storage = _FakeStorage()

    async def compress(_file: bytes, *, level: int):
        return SimpleNamespace(
            data=b'larger-or-equal',
            suffix='.zst',
            metadata={'zstd_level': str(level)},
        )

    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_service, 'db', _FakeDB(rowcount=1))
    monkeypatch.setattr(trace_service.TraceFile, 'compress', compress)

    await trace_service._recompress_trace_file(
        TraceId(123), StorageKey('old.zst'), b'content', compressed_size=1
    )

    assert storage.saved == []
    assert storage.deleted == []
