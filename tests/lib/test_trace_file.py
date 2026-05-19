from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_compression():
    result = await TraceFile.compress(b'hello')
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == b'hello'
    )
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test')) != b'hello'


async def test_trace_file_compression_uses_requested_level(monkeypatch):
    from app.lib.io import trace_file

    captured_options = {}

    def fake_compress(buffer: bytes, *, options):
        captured_options.update(options)
        return buffer

    monkeypatch.setattr(trace_file.zstd, 'compress', fake_compress)

    result = await TraceFile.compress(b'hello', level=22, threads=1)

    assert result.data == b'hello'
    assert result.metadata == {'zstd_level': '22'}
    assert (
        captured_options[trace_file.zstd.CompressionParameter.compression_level]
        == 22
    )
    assert captured_options[trace_file.zstd.CompressionParameter.nb_workers] == 1
