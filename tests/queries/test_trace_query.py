from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

import app.queries.trace_query as query
from app.models.types import StorageKey, TraceId


@pytest.mark.parametrize(
    'state', ['unchanged', 'replaced', 'missing', 'private', 'storage_error', 'success']
)
async def test_trace_download_during_recompression(monkeypatch, state):
    old_trace = {'file_id': StorageKey('old.zst')}
    new_trace = {'file_id': StorageKey('new.zst')}
    missing_file = FileNotFoundError('old.zst')
    traces = [old_trace]
    if state == 'missing':
        traces.append(None)
    elif state == 'unchanged':
        traces.append(old_trace)
    else:
        traces.append(new_trace)
    fetch = AsyncMock(side_effect=traces)
    load = AsyncMock(
        side_effect=[b'compressed']
        if state == 'success'
        else [
            missing_file,
            RuntimeError('storage unavailable')
            if state == 'storage_error'
            else b'compressed',
        ]
    )
    monkeypatch.setattr(query, 'db_fetchone', fetch)
    monkeypatch.setattr(
        query,
        'trace_is_visible',
        lambda trace: state != 'private' or trace is old_trace,
    )
    monkeypatch.setattr(query, 'TRACE_STORAGE', SimpleNamespace(load=load))
    monkeypatch.setattr(
        query,
        'raise_for',
        SimpleNamespace(
            trace_not_found=Mock(side_effect=LookupError),
            trace_access_denied=Mock(side_effect=PermissionError),
        ),
    )
    decompress = Mock(return_value=b'original upload')
    monkeypatch.setattr(query.TraceFile, 'decompress_if_needed', decompress)

    if state in {'success', 'replaced'}:
        result = await query.TraceQuery.get_one_data_by_id(TraceId(123))
        assert result == b'original upload'
        decompress.assert_called_once_with(
            b'compressed', 'old.zst' if state == 'success' else 'new.zst'
        )
    else:
        error = {
            'unchanged': FileNotFoundError,
            'missing': LookupError,
            'private': PermissionError,
            'storage_error': RuntimeError,
        }[state]
        with pytest.raises(error):
            await query.TraceQuery.get_one_data_by_id(TraceId(123))
        decompress.assert_not_called()

    assert load.await_args_list == (
        [call('old.zst'), call('new.zst')]
        if state in {'replaced', 'storage_error'}
        else [call('old.zst')]
    )
    assert fetch.await_count == (1 if state == 'success' else 2)
