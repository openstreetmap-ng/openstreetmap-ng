from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import changeset_service
from app.services.changeset_service import ChangesetService
from app.services.note_service import NoteService


@pytest.fixture
def workflow(monkeypatch):
    conn = object()
    events = []

    @asynccontextmanager
    async def database(*_args, **_kwargs):
        events.append('begin')
        try:
            yield conn
        except Exception:
            events.append('rollback')
            raise
        else:
            events.append('commit')

    async def close(tags, shared_conn):
        assert shared_conn is conn
        assert events[-1] == 'begin'
        return [tags]

    async def notify(_comments):
        assert events[-1] == 'commit'

    closer = AsyncMock(side_effect=close)
    notifier = AsyncMock(side_effect=notify)
    fetch = AsyncMock(return_value=(7, None, {'closes:note': '1'}))
    monkeypatch.setattr(changeset_service, 'db', database)
    monkeypatch.setattr(changeset_service, 'db_fetchrow', fetch)
    monkeypatch.setattr(changeset_service, 'db_update', AsyncMock())
    monkeypatch.setattr(changeset_service, 'audit', AsyncMock())
    monkeypatch.setattr(changeset_service, 'auth_user', lambda **_kwargs: {'id': 7})
    monkeypatch.setattr(NoteService, 'close_for_changeset', closer)
    monkeypatch.setattr(NoteService, 'notify_comments', notifier)
    return events, fetch, closer, notifier


async def test_explicit_close_notifies_after_commit(workflow):
    events, _fetch, closer, notifier = workflow
    await ChangesetService.close(1)
    assert events == ['begin', 'commit']
    closer.assert_awaited_once()
    notifier.assert_awaited_once()


async def test_note_error_rolls_back_changeset_and_never_notifies(workflow):
    events, _fetch, closer, notifier = workflow
    closer.side_effect = RuntimeError('write failed')
    with pytest.raises(RuntimeError, match='write failed'):
        await ChangesetService.close(1)
    assert events == ['begin', 'rollback']
    notifier.assert_not_awaited()


async def test_other_owner_cannot_trigger_note_closing(workflow, monkeypatch):
    events, fetch, closer, notifier = workflow
    fetch.return_value = (8, None, {'closes:note': '1'})

    def deny():
        raise ValueError('access denied')

    monkeypatch.setattr(
        changeset_service, 'raise_for', SimpleNamespace(changeset_access_denied=deny)
    )
    with pytest.raises(ValueError, match='access denied'):
        await ChangesetService.close(1)
    assert events == ['begin', 'rollback']
    closer.assert_not_awaited()
    notifier.assert_not_awaited()


async def test_inactive_close_uses_owner_and_skips_anonymous(workflow, monkeypatch):
    events, _fetch, closer, notifier = workflow
    changesets = [
        {'user_id': None, 'tags': {'closes:note': '1'}},
        {'user_id': 9, 'tags': {}},
        {'user_id': 7, 'tags': {'closes:note': '2'}},
    ]
    contexts = []

    @contextmanager
    def context(user):
        contexts.append(user['id'])
        yield

    lookup = AsyncMock(return_value={'id': 7})
    monkeypatch.setattr(
        changeset_service, 'db_fetchall', AsyncMock(return_value=changesets)
    )
    monkeypatch.setattr(
        changeset_service, 'UserQuery', SimpleNamespace(find_by_id=lookup)
    )
    monkeypatch.setattr(changeset_service, 'auth_context', context)
    await changeset_service._close_inactive()  # noqa: SLF001
    assert events == ['begin', 'commit']
    lookup.assert_awaited_once_with(7)
    closer.assert_awaited_once()
    notifier.assert_awaited_once()
    assert contexts == [7, 7]
