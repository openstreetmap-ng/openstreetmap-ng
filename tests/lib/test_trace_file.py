from asyncio import gather

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


async def test_trace_file_compression_levels():
    original = b'<gpx><trk>original uploaded bytes</trk></gpx>' * 100
    fast, slow = await gather(
        TraceFile.compress(original), TraceFile.compress(original, level=22)
    )
    assert fast.metadata == {'zstd_level': str(TRACE_FILE_COMPRESS_ZSTD_LEVEL)}
    assert slow.metadata == {'zstd_level': '22'}
    for result in (fast, slow):
        assert (
            TraceFile.decompress_if_needed(
                result.data, StorageKey('test' + result.suffix)
            )
            == original
        )
    # A background call must not change subsequent foreground compression options.
    assert (await TraceFile.compress(original)).metadata == fast.metadata
