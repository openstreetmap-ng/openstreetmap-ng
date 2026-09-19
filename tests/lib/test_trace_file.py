from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_compression():
    result = await TraceFile.compress(b'hello')
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == b'hello'
    )
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test')) != b'hello'


async def test_trace_file_heavy_compression_preserves_data_and_metadata():
    data = b'<gpx><trk><trkseg><trkpt lat="1" lon="2"/></trkseg></trk></gpx>' * 8
    heavy = await TraceFile.compress(data, level=22)
    assert heavy.metadata == {'zstd_level': '22'}
    assert TraceFile.decompress_if_needed(heavy.data, StorageKey('test.zst')) == data
    normal = await TraceFile.compress(data)
    assert normal.metadata == {'zstd_level': '6'}
