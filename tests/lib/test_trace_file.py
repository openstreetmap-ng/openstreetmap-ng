from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_compression():
    result = await TraceFile.compress(b'hello')
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == b'hello'
    )
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test')) != b'hello'


async def test_trace_file_compression_level_metadata():
    result = await TraceFile.compress(b'hello', level=22)

    assert result.metadata['zstd_level'] == '22'
