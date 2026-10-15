from compression import zstd
from threading import get_ident

from app.config import TRACE_FILE_COMPRESS_ZSTD_LEVEL, TRACE_FILE_COMPRESS_ZSTD_THREADS
from app.lib.io.trace_file import TraceFile
from app.models.types import StorageKey


async def test_trace_file_compression():
    result = await TraceFile.compress(b'hello')
    assert (
        TraceFile.decompress_if_needed(result.data, StorageKey('test' + result.suffix))
        == b'hello'
    )
    assert TraceFile.decompress_if_needed(result.data, StorageKey('test')) != b'hello'


async def test_trace_file_recompression_level_does_not_change_default():
    buffer = b'<gpx><trk><name>unchanged upload bytes</name></trk></gpx>' * 20
    recompressed = await TraceFile.compress(buffer, level=22)
    initial = await TraceFile.compress(buffer)
    assert recompressed.metadata == {'zstd_level': '22'}
    assert initial.metadata == {'zstd_level': str(TRACE_FILE_COMPRESS_ZSTD_LEVEL)}
    for result in (recompressed, initial):
        assert (
            TraceFile.decompress_if_needed(
                result.data, StorageKey('test' + result.suffix)
            )
            == buffer
        )


async def test_trace_file_recompression_uses_thread_and_level_22(monkeypatch):
    main_thread = get_ident()
    compress = zstd.compress
    calls = []

    def record_compress(buffer, *, options):
        calls.append((get_ident(), options.copy()))
        return compress(buffer, options=options)

    monkeypatch.setattr(zstd, 'compress', record_compress)
    result = await TraceFile.compress(b'original bytes', level=22)
    assert zstd.decompress(result.data) == b'original bytes'
    assert len(calls) == 1
    thread_id, options = calls[0]
    assert thread_id != main_thread
    assert options[zstd.CompressionParameter.compression_level] == 22
    assert (
        options[zstd.CompressionParameter.nb_workers]
        == TRACE_FILE_COMPRESS_ZSTD_THREADS
    )
