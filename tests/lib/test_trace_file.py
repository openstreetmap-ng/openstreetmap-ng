from app.config import (
    TRACE_FILE_COMPRESS_ZSTD_LEVEL,
    TRACE_FILE_RECOMPRESS_ZSTD_LEVEL,
)
from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_compression():
    result = await TraceFile.compress(b'hello')
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == b'hello'
    )
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test')) != b'hello'
    assert result.metadata == {'zstd_level': str(TRACE_FILE_COMPRESS_ZSTD_LEVEL)}

    recompressed = await TraceFile.compress(
        b'hello', level=TRACE_FILE_RECOMPRESS_ZSTD_LEVEL
    )
    assert (
        TraceFile.decompress_if_needed(
            recompressed.data, StorageKey('test' + recompressed.suffix)
        )
        == b'hello'
    )
    assert recompressed.metadata == {
        'zstd_level': str(TRACE_FILE_RECOMPRESS_ZSTD_LEVEL)
    }
