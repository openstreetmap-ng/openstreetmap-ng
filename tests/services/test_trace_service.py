from types import SimpleNamespace

from app.models.types import StorageKey, TraceId
from app.services import trace_upload_compression


async def test_compress_trace_upload_swaps_file_reference(monkeypatch):
    saved: list[tuple[bytes, str, dict[str, str] | None]] = []
    deleted: list[StorageKey] = []
    updates: list[tuple[str, dict, dict]] = []

    class Storage:
        async def save(
            self,
            data: bytes,
            suffix: str,
            metadata: dict[str, str] | None = None,
        ):
            saved.append((data, suffix, metadata))
            return StorageKey(f'compressed{suffix}')

        async def delete(self, key: StorageKey):
            deleted.append(key)

    async def compress(file: bytes):
        assert file == b'original'
        return SimpleNamespace(
            data=b'compressed',
            suffix='.zst',
            metadata={'zstd_level': '22'},
        )

    async def db_update(table: str, values: dict, where: dict):
        updates.append((table, values, where))
        return 1

    monkeypatch.setattr(trace_upload_compression.TraceFile, 'compress', compress)
    monkeypatch.setattr(trace_upload_compression, 'TRACE_STORAGE', Storage())
    monkeypatch.setattr(trace_upload_compression, 'db_update', db_update)

    await trace_upload_compression.compress_trace_upload(
        TraceId(1),
        StorageKey('original'),
        b'original',
    )

    assert saved == [(b'compressed', '.zst', {'zstd_level': '22'})]
    assert updates == [
        (
            'trace',
            {'file_id': StorageKey('compressed.zst')},
            {'id': TraceId(1), 'file_id': StorageKey('original')},
        )
    ]
    assert deleted == [StorageKey('original')]


async def test_compress_trace_upload_deletes_compressed_file_if_trace_changed(
    monkeypatch,
):
    deleted: list[StorageKey] = []

    class Storage:
        async def save(
            self,
            data: bytes,
            suffix: str,
            metadata: dict[str, str] | None = None,
        ):
            return StorageKey(f'compressed{suffix}')

        async def delete(self, key: StorageKey):
            deleted.append(key)

    async def compress(_: bytes):
        return SimpleNamespace(data=b'compressed', suffix='.zst', metadata={})

    async def db_update(table: str, values: dict, where: dict):
        return 0

    monkeypatch.setattr(trace_upload_compression.TraceFile, 'compress', compress)
    monkeypatch.setattr(trace_upload_compression, 'TRACE_STORAGE', Storage())
    monkeypatch.setattr(trace_upload_compression, 'db_update', db_update)

    await trace_upload_compression.compress_trace_upload(
        TraceId(1),
        StorageKey('original'),
        b'original',
    )

    assert deleted == [StorageKey('compressed.zst')]
