from app.lib.io import trace_file
from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_compression():
    result = await TraceFile.compress(b'hello')
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == b'hello'
    )
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test')) != b'hello'


def test_trace_file_compression_level_metadata():
    options = trace_file._zstd_options(22)  # noqa: SLF001

    assert options[trace_file.zstd.CompressionParameter.compression_level] == 22
    assert trace_file._zstd_metadata(22) == {'zstd_level': '22'}  # noqa: SLF001
