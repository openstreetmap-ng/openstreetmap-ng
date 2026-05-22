from typing import NamedTuple

import pytest

from app.lib.io import trace_file as trace_file_module

if str(trace_file_module.__file__).endswith(('.pyd', '.so')):
    pytest.skip(
        'Cython/coverage finalization aborts after importing this async worker',
        allow_module_level=True,
    )

from app.background import trace_recompression as trace_recompression_module
from app.background.trace_recompression import (
    _compress_trace_file,
    _recompress_trace_file,
)
from app.config import TRACE_FILE_RECOMPRESS_ZSTD_LEVEL
from app.models.types import StorageKey, TraceId


class _FakeCompressResult(NamedTuple):
    data: bytes
    suffix: str
    metadata: dict[str, str]


class _FakeTraceStorage:
    def __init__(self):
        self.saved: list[tuple[StorageKey, bytes, str, dict[str, str]]] = []
        self.deleted: list[StorageKey] = []

    async def save(self, data: bytes, suffix: str, metadata: dict[str, str]):
        key = StorageKey(f'trace-{len(self.saved)}{suffix}')
        self.saved.append((key, data, suffix, metadata))
        return key

    async def delete(self, key: StorageKey):
        self.deleted.append(key)


async def test_trace_recompression_level(monkeypatch):
    calls = []

    def fake_compress(buffer, *, options):
        calls.append((buffer, options))
        return b'compressed'

    monkeypatch.setattr(trace_recompression_module.zstd, 'compress', fake_compress)

    result = await _compress_trace_file(b'hello')

    assert result.metadata == {'zstd_level': str(TRACE_FILE_RECOMPRESS_ZSTD_LEVEL)}
    assert result.data == b'compressed'
    assert calls[0][0] == b'hello'
    assert (
        calls[0][1][
            trace_recompression_module.zstd.CompressionParameter.compression_level
        ]
        == TRACE_FILE_RECOMPRESS_ZSTD_LEVEL
    )


async def test_recompress_trace_file_swaps_file_id(monkeypatch):
    storage = _FakeTraceStorage()
    updates = []

    async def fake_db_update(table, values, *, where, conn=None):
        updates.append((table, values, where))
        return 1

    monkeypatch.setattr(trace_recompression_module, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_recompression_module, 'db_update', fake_db_update)
    monkeypatch.setattr(
        trace_recompression_module,
        '_compress_trace_file',
        _fake_recompress,
    )

    old_file_id = StorageKey('old.zst')
    await _recompress_trace_file(TraceId(1), old_file_id, b'hello')

    new_file_id, data, suffix, metadata = storage.saved[0]
    assert suffix == '.zst'
    assert metadata == {'zstd_level': '22'}
    assert data == b'recompressed:hello'
    assert updates == [
        ('trace', {'file_id': new_file_id}, {'id': TraceId(1), 'file_id': old_file_id})
    ]
    assert storage.deleted == [old_file_id]


async def test_recompress_trace_file_discards_new_file_when_trace_changed(
    monkeypatch,
):
    storage = _FakeTraceStorage()

    async def fake_db_update(table, values, *, where, conn=None):
        return 0

    monkeypatch.setattr(trace_recompression_module, 'TRACE_STORAGE', storage)
    monkeypatch.setattr(trace_recompression_module, 'db_update', fake_db_update)
    monkeypatch.setattr(
        trace_recompression_module,
        '_compress_trace_file',
        _fake_recompress,
    )

    old_file_id = StorageKey('old.zst')
    await _recompress_trace_file(TraceId(1), old_file_id, b'hello')

    new_file_id = storage.saved[0][0]
    assert storage.deleted == [new_file_id]


async def _fake_recompress(buffer: bytes):
    return _FakeCompressResult(
        b'recompressed:' + buffer,
        '.zst',
        {'zstd_level': str(TRACE_FILE_RECOMPRESS_ZSTD_LEVEL)},
    )
