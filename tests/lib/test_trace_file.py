from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_compression():
    result = await TraceFile.compress(b'hello')
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == b'hello'
    )
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test')) != b'hello'


async def test_trace_file_recompression():
    """Recompress with heavy zstd (level 22) should produce valid compressed data that decompresses correctly."""
    original = b'test trace file data for recompression' * 100
    result = await TraceFile.recompress(original)
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == original
    )
    # Heavy compression should produce smaller or equal output than light compression
    light = await TraceFile.compress(original)
    assert len(result.data) <= len(light.data)
