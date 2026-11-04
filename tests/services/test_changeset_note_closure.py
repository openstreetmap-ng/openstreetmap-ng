from datetime import timedelta

import pytest

from app.config import CHANGESET_IDLE_TIMEOUT
from app.db import db, db_fetchrow, db_update
from app.lib.auth.context import auth_context
from app.lib.time.date_utils import utcnow
from app.models.types import DisplayName
from app.queries.user_query import UserQuery
from app.services.changeset_service import ChangesetService, _close_inactive
from app.services.note_service import NoteService


@pytest.mark.parametrize('inactive', [False, True])
async def test_changeset_closes_notes(inactive):
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None
    with auth_context(user, frozenset(('web_user',))):
        note_id = await NoteService.create(0, 0, 'Close with changeset')
        changeset_id = await ChangesetService.create({
            'closes:note': f'{note_id};{note_id}',
            'comment': 'default',
            f'closes:note:{note_id}:comment': 'specific',
        })
        if inactive:
            await db_update(
                'changeset',
                {
                    'updated_at': utcnow()
                    - CHANGESET_IDLE_TIMEOUT
                    - timedelta(seconds=1),
                    'size': 1,
                },
                where={'id': changeset_id},
            )
            await _close_inactive()
        else:
            await ChangesetService.close(changeset_id)
        row = await db_fetchrow(t'SELECT closed_at FROM note WHERE id = {note_id}')
        assert row is not None and row[0] is not None
        row = await db_fetchrow(t"""
            SELECT count(*), min(body), min(user_id) FROM note_comment
            WHERE note_id = {note_id} AND event = 'closed'
        """)
        assert row == (1, 'specific', user['id'])
        # Closing another changeset must not duplicate an already-closed note.
        other_id = await ChangesetService.create({'closes:note': str(note_id)})
        await ChangesetService.close(other_id)
        row = await db_fetchrow(
            t"SELECT count(*) FROM note_comment WHERE note_id = {note_id} AND event = 'closed'"
        )
        assert row == (1,)


async def test_changeset_note_closure_rolls_back():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None
    with auth_context(user, frozenset(('web_user',))):
        note_id = await NoteService.create(0, 0, 'Must stay open')
        with pytest.raises(RuntimeError, match='rollback'):  # noqa: PT012
            async with db(True) as conn:
                await NoteService.close_from_changeset(
                    conn, user['id'], {'closes:note': str(note_id)}
                )
                raise RuntimeError('rollback')
        row = await db_fetchrow(t'SELECT closed_at FROM note WHERE id = {note_id}')
        assert row == (None,)
