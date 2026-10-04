from types import SimpleNamespace

from app.services import trace_service


async def test_recompress_trace_file_swaps_and_deletes_old(monkeypatch):
    saved: list[tuple[bytes, str, dict[str, str]]] = []
    deleted: list[str] = []
    updates: list[tuple[dict[str, str], dict[str, object]]] = []

    class Storage:
        async def save(self, data: bytes, suffix: str, metadata: dict[str, str]):
            saved.append((data, suffix, metadata))
            return 'new.zst'

        async def delete(self, key: str):
            deleted.append(key)

    async def compress(file: bytes, *, level: int):
        assert file == b'gpx'
        assert level == 22
        return SimpleNamespace(
            data=b'compressed',
            suffix='.zst',
            metadata={'zstd_level': '22'},
        )

    async def db_update(table, values, *, where):
        assert table == 'trace'
        updates.append((values, where))
        return 1

    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', Storage())
    monkeypatch.setattr(trace_service.TraceFile, 'compress', compress)
    monkeypatch.setattr(trace_service, 'db_update', db_update)

    await trace_service._recompress_trace_file(1, b'gpx', 'old.zst')  # noqa: SLF001

    assert saved == [(b'compressed', '.zst', {'zstd_level': '22'})]
    assert updates == [({'file_id': 'new.zst'}, {'id': 1, 'file_id': 'old.zst'})]
    assert deleted == ['old.zst']


async def test_recompress_trace_file_discards_new_file_when_trace_changed(monkeypatch):
    deleted: list[str] = []

    class Storage:
        async def save(self, data: bytes, suffix: str, metadata: dict[str, str]):
            return 'new.zst'

        async def delete(self, key: str):
            deleted.append(key)

    async def compress(file: bytes, *, level: int):
        return SimpleNamespace(data=b'compressed', suffix='.zst', metadata={})

    async def db_update(table, values, *, where):
        return 0

    monkeypatch.setattr(trace_service, 'TRACE_STORAGE', Storage())
    monkeypatch.setattr(trace_service.TraceFile, 'compress', compress)
    monkeypatch.setattr(trace_service, 'db_update', db_update)

    await trace_service._recompress_trace_file(1, b'gpx', 'old.zst')  # noqa: SLF001

    assert deleted == ['new.zst']
