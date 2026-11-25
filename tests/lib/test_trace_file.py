from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_high_compression():
    data = b'<trkpt lat="51.5" lon="-0.1" />' * 1000
    result = await TraceFile.compress(data, level=22)
    assert result.metadata == {'zstd_level': '22'}
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test.zst')) == data
    default = await TraceFile.compress(data)
    assert default.metadata == {'zstd_level': '6'}


async def test_trace_file_compression():
    result = await TraceFile.compress(b'hello')
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == b'hello'
    )
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test')) != b'hello'
