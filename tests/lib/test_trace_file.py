import pytest

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
async def test_trace_compression_level(level: int):
    original = (
        b'<gpx><trk><trkseg>'
        + b'<trkpt lat="1" lon="2"/>' * 100
        + b'</trkseg></trk></gpx>'
    )
    result = await TraceFile.compress(original, level=level)
    assert result.metadata == {'zstd_level': str(level)}
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test.zst')) == original
    )
