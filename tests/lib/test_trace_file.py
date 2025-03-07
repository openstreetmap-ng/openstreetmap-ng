from app.lib.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_compression():
    compressed, suffix = await TraceFile.compress(b'hello')
    assert TraceFile.decompress_if_needed(compressed, StorageKey('test' + suffix)) == b'hello'
    assert TraceFile.decompress_if_needed(compressed, StorageKey('test')) != b'hello'
