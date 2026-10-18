from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import app.queries.trace_query as query
from app.models.types import StorageKey, TraceId


@pytest.mark.parametrize('state', ['visible', 'private', 'missing'])
async def test_trace_download_holds_lock_during_storage_read(monkeypatch, state):
    events = []
    trace = {'file_id': StorageKey('trace.zst')} if state != 'missing' else None

    @asynccontextmanager
    async def transaction(*_args):
        events.append('begin')
        yield None
        events.append('commit')

    async def load(file_id):
        assert file_id == 'trace.zst'
        assert events == ['begin']
        events.append('load')
        return b'compressed'

    fetch = AsyncMock(return_value=trace)
    storage = SimpleNamespace(load=AsyncMock(side_effect=load))
    monkeypatch.setattr(query, 'db', transaction)
    monkeypatch.setattr(query, 'db_fetchone', fetch)
    monkeypatch.setattr(query, 'trace_is_visible', lambda _trace: state == 'visible')
    monkeypatch.setattr(query, 'TRACE_STORAGE', storage)
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

    if state == 'visible':
        result = await query.TraceQuery.get_one_data_by_id(TraceId(123))
        assert result == b'original upload'
        assert events == ['begin', 'load', 'commit']
        decompress.assert_called_once_with(b'compressed', 'trace.zst')
    else:
        error = LookupError if state == 'missing' else PermissionError
        with pytest.raises(error):
            await query.TraceQuery.get_one_data_by_id(TraceId(123))
        storage.load.assert_not_awaited()
        decompress.assert_not_called()

    assert 'FOR SHARE' in ''.join(fetch.await_args.args[1].strings)
