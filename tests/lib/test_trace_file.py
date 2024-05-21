from app.lib.trace_file import TraceFile


def test_trace_file_compression():
    compressed, suffix = TraceFile.compress(b'hello')
    file_id = 'test' + suffix
    assert TraceFile.decompress_if_needed(compressed, file_id) == b'hello'
    assert TraceFile.decompress_if_needed(compressed, '') != b'hello'
