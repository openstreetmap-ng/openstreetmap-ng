from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import note_service
from app.services.note_service import NoteService


@pytest.fixture
def mutation(monkeypatch):
    user = {'id': 12, 'display_name': 'mapper', 'roles': []}
    conn = object()

    @asynccontextmanager
    async def database(write=True, passed_conn=None):
        assert write is True
        if passed_conn is not None:
            assert passed_conn is conn
        yield conn

    note = {'id': 7, 'hidden_at': None, 'closed_at': None}
    now = datetime.now(UTC)
    fetch = AsyncMock(return_value=note)
    insert = AsyncMock(return_value=(91, now))
    update = AsyncMock()
    audit = AsyncMock()
    monkeypatch.setattr(note_service, 'db', database)
    monkeypatch.setattr(note_service, 'auth_user', lambda **_kwargs: user)
    monkeypatch.setattr(note_service, 'user_is_moderator', lambda _user: False)
    monkeypatch.setattr(note_service, 'db_fetchone', fetch)
    monkeypatch.setattr(note_service, 'db_insert', insert)
    monkeypatch.setattr(note_service, 'db_update', update)
    monkeypatch.setattr(note_service, 'audit', audit)
    return conn, fetch, insert, update, audit


@pytest.mark.parametrize(
    'note',
    [
        None,
        {'closed_at': True, 'hidden_at': None},
        {'closed_at': None, 'hidden_at': True},
    ],
)
async def test_skip_unavailable_without_mutation(mutation, note):
    conn, fetch, insert, update, audit = mutation
    fetch.return_value = note
    assert await NoteService.close_for_changeset({'closes:note': '7'}, conn) == []
    insert.assert_not_awaited()
    update.assert_not_awaited()
    audit.assert_not_awaited()


async def test_close_writes_owner_comment_in_shared_transaction(mutation):
    conn, fetch, insert, update, audit = mutation
    result = await NoteService.close_for_changeset(
        {'closes:note': '7;7', 'comment': 'Mapped'}, conn
    )
    assert len(result) == 1
    insert.assert_awaited_once()
    values = insert.call_args.args[1]
    assert values == {
        'user_id': 12,
        'user_ip': None,
        'note_id': 7,
        'event': 'closed',
        'body': 'Mapped',
    }
    assert insert.call_args.kwargs['conn'] is conn
    assert update.call_args.kwargs['conn'] is conn
    assert fetch.call_args.kwargs['conn'] is conn
    assert len(audit.await_args_list) == 2
    assert result[0][1]['user']['id'] == 12
    assert result[0][2] is True


async def test_regular_close_still_rejects_already_closed(mutation, monkeypatch):
    _conn, fetch, insert, _update, _audit = mutation
    fetch.return_value = {'closed_at': True, 'hidden_at': None}
    error = Mock(side_effect=ValueError('already closed'))
    monkeypatch.setattr(note_service, 'raise_for', SimpleNamespace(note_closed=error))
    with pytest.raises(ValueError, match='already closed'):
        await NoteService.comment(7, 'Mapped', 'closed')
    insert.assert_not_awaited()


async def test_unexpected_database_error_propagates(mutation):
    conn, _fetch, insert, _update, _audit = mutation
    insert.side_effect = RuntimeError('database failed')
    with pytest.raises(RuntimeError, match='database failed'):
        await NoteService.close_for_changeset({'closes:note': '7'}, conn)


async def test_regular_comment_notifies_after_own_transaction(mutation, monkeypatch):
    conn, _fetch, _insert, _update, _audit = mutation
    committed = False

    @asynccontextmanager
    async def database(write=True, passed_conn=None):
        nonlocal committed
        yield conn
        committed = True

    async def notify(results):
        assert committed
        assert len(results) == 1

    monkeypatch.setattr(note_service, 'db', database)
    notifications = AsyncMock(side_effect=notify)
    monkeypatch.setattr(NoteService, 'notify_comments', notifications)
    await NoteService.comment(7, 'Mapped', 'closed')
    notifications.assert_awaited_once()
