import pytest

from app.config import TRACE_FILE_COMPRESS_ZSTD_LEVEL
from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_compression():
    result = await TraceFile.compress(b'hello')
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == b'hello'
    )
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test')) != b'hello'


@pytest.mark.parametrize('level', [1, 22])
async def test_trace_file_compression_level(level):
    result = await TraceFile.compress(b'hello', level=level)
    assert result.metadata == {'zstd_level': str(level)}
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test.zst')) == b'hello'
    )
    default = await TraceFile.compress(b'hello')
    assert default.metadata == {'zstd_level': str(TRACE_FILE_COMPRESS_ZSTD_LEVEL)}
