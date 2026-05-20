from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_compression():
    result = await TraceFile.compress(b'hello')
    assert result.metadata['zstd_level'] == '6'
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == b'hello'
    )
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test')) != b'hello'

    background_result = await TraceFile.recompress(b'hello')
    assert background_result.metadata['zstd_level'] == '22'
    assert (
        TraceFile.decompress_if_needed(
            background_result.data, StorageKey('test' + background_result.suffix)
        )
        == b'hello'
    )
