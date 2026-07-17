from datetime import datetime, timedelta
from typing import Any

from psycopg.sql import SQL, Identifier
from shapely import Point

from app.config import (
    CHANGESET_EMPTY_DELETE_TIMEOUT,
    CHANGESET_IDLE_TIMEOUT,
    CHANGESET_OPEN_TIMEOUT,
)
from app.db import db, db_fetchone, db_insert
from app.exceptions.api06 import Exceptions06
from app.exceptions.context import exceptions_context
from app.lib.auth.context import auth_context
from app.lib.time.date_utils import utcnow
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.types import ChangesetId, DisplayName, NoteId, UserId
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_query import UserQuery
from app.services.changeset_service import ChangesetService
from app.services.note_service import NoteService


async def test_changeset_inactive_close():
    # Create a changeset that's been inactive for longer than the idle timeout
    inactive_time = utcnow() - CHANGESET_IDLE_TIMEOUT - timedelta(seconds=1)
    changeset_id = await _create_changeset(updated_at=inactive_time)

    # Verify it exists and is open
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Changeset must exist'
    assert changeset['closed_at'] is None, 'Changeset must be open initially'

    # Force process to close inactive changesets
    await ChangesetService.force_process()

    # Verify it's been closed
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Changeset must still exist'
    assert changeset['closed_at'] is not None, (
        'Changeset must be closed after processing'
    )


async def test_changeset_inactive_open():
    # Create a changeset that's been active more recently than the idle timeout
    recent_time = utcnow() - CHANGESET_IDLE_TIMEOUT + timedelta(minutes=1)
    changeset_id = await _create_changeset(updated_at=recent_time)

    # Verify it exists and is open
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Changeset must exist'
    assert changeset['closed_at'] is None, 'Changeset must be open initially'

    # Force process
    await ChangesetService.force_process()

    # Verify it's still open
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Changeset must still exist'
    assert changeset['closed_at'] is None, 'Recently active changeset must remain open'


async def test_changeset_open_timeout_close():
    # Create a changeset that's been open for longer than the open timeout but recently active
    old_created_at = utcnow() - CHANGESET_OPEN_TIMEOUT - timedelta(seconds=1)
    recent_updated_at = utcnow()
    changeset_id = await _create_changeset(
        created_at=old_created_at, updated_at=recent_updated_at
    )

    # Verify it exists and is open
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Changeset must exist'
    assert changeset['closed_at'] is None, 'Changeset must be open initially'

    # Force process
    await ChangesetService.force_process()

    # Verify it's been closed despite recent activity
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Changeset must still exist'
    assert changeset['closed_at'] is not None, (
        'Old changeset must be closed even if recently active'
    )


async def test_changeset_open_timeout_open():
    # Create a changeset that's been open for less than the open timeout
    recent_created_at = utcnow() - CHANGESET_OPEN_TIMEOUT + timedelta(minutes=1)
    changeset_id = await _create_changeset(created_at=recent_created_at)

    # Verify it exists and is open
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Changeset must exist'
    assert changeset['closed_at'] is None, 'Changeset must be open initially'

    # Force process
    await ChangesetService.force_process()

    # Verify it's still open
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Changeset must still exist'
    assert changeset['closed_at'] is None, 'Recent changeset must remain open'


async def test_changeset_delete_empty():
    # Create an empty changeset that was closed longer ago than the delete timeout
    old_time = utcnow() - CHANGESET_EMPTY_DELETE_TIMEOUT - timedelta(seconds=1)
    changeset_id = await _create_changeset(
        created_at=old_time, updated_at=old_time, closed_at=old_time
    )

    # Verify it exists
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Changeset must exist initially'

    # Force process
    await ChangesetService.force_process()

    # Verify it's been deleted
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is None, 'Old empty changeset must be deleted'


async def test_changeset_dont_delete_empty_recent():
    # Create an empty changeset that was closed more recently than the delete timeout
    recent_time = utcnow() - CHANGESET_EMPTY_DELETE_TIMEOUT + timedelta(minutes=1)
    changeset_id = await _create_changeset(
        created_at=recent_time, updated_at=recent_time, closed_at=recent_time
    )

    # Verify it exists
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Changeset must exist initially'

    # Force process
    await ChangesetService.force_process()

    # Verify it still exists
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    assert changeset is not None, 'Recent empty changeset must not be deleted'


# === Tests for closes:note tag processing (issue #126) ===


async def test_changeset_close_closes_tagged_notes():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None, 'Test user "user1" must exist'
    user_id = user['id']

    note_id = await _create_note(user_id, 'issue reported')
    changeset_id = await _create_changeset(
        user_id=user_id,
        tags={'closes:note': str(note_id), 'closes:note:comment': 'resolved'},
    )

    with exceptions_context(Exceptions06()), auth_context(user):
        await ChangesetService.close(changeset_id)

    note = await _get_note(note_id)
    assert note is not None, 'Note must exist'
    assert note['closed_at'] is not None, 'Note must be closed after changeset close'

    comment = await _get_close_comment(note_id)
    assert comment is not None, 'Close comment must exist'
    assert comment['event'] == 'closed'
    assert comment['body'] == 'resolved'
    assert comment['user_id'] == user_id


async def test_changeset_close_tagged_notes_per_note_comment():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None, 'Test user "user1" must exist'
    user_id = user['id']

    note_id = await _create_note(user_id)
    changeset_id = await _create_changeset(
        user_id=user_id,
        tags={
            'closes:note': str(note_id),
            'closes:note:comment': 'global default',
            f'closes:note:{note_id}:comment': 'per-note override',
        },
    )

    with exceptions_context(Exceptions06()), auth_context(user):
        await ChangesetService.close(changeset_id)

    comment = await _get_close_comment(note_id)
    assert comment is not None, 'Close comment must exist'
    assert comment['body'] == 'per-note override'


async def test_changeset_close_tagged_notes_global_comment():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None, 'Test user "user1" must exist'
    user_id = user['id']

    note1_id = await _create_note(user_id)
    note2_id = await _create_note(user_id)
    changeset_id = await _create_changeset(
        user_id=user_id,
        tags={
            'closes:note': f'{note1_id};{note2_id}',
            'closes:note:comment': 'global comment text',
        },
    )

    with exceptions_context(Exceptions06()), auth_context(user):
        await ChangesetService.close(changeset_id)

    c1 = await _get_close_comment(note1_id)
    assert c1 is not None, 'Close comment for note1 must exist'
    assert c1['body'] == 'global comment text'

    c2 = await _get_close_comment(note2_id)
    assert c2 is not None, 'Close comment for note2 must exist'
    assert c2['body'] == 'global comment text'


async def test_changeset_close_tagged_notes_changeset_comment():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None, 'Test user "user1" must exist'
    user_id = user['id']

    note_id = await _create_note(user_id)
    changeset_id = await _create_changeset(
        user_id=user_id,
        tags={
            'closes:note': str(note_id),
            'comment': 'changeset comment text',
        },
    )

    with exceptions_context(Exceptions06()), auth_context(user):
        await ChangesetService.close(changeset_id)

    comment = await _get_close_comment(note_id)
    assert comment is not None, 'Close comment must exist'
    assert comment['body'] == 'changeset comment text'


async def test_changeset_close_tagged_notes_no_comment():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None, 'Test user "user1" must exist'
    user_id = user['id']

    note_id = await _create_note(user_id)
    changeset_id = await _create_changeset(
        user_id=user_id,
        tags={'closes:note': str(note_id)},
    )

    with exceptions_context(Exceptions06()), auth_context(user):
        await ChangesetService.close(changeset_id)

    note = await _get_note(note_id)
    assert note is not None, 'Note must exist'
    assert note['closed_at'] is not None, 'Note must be closed even without comment'

    comment = await _get_close_comment(note_id)
    assert comment is not None, 'Close comment must exist'
    assert comment['event'] == 'closed'
    assert comment['body'] == ''


async def test_changeset_close_tagged_notes_already_closed():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None, 'Test user "user1" must exist'
    user_id = user['id']

    note_id = await _create_note(user_id)

    # Close the note first using close_if_open directly
    async with db(True) as conn:
        closed = await NoteService.close_if_open(
            note_id, 'first close', user_id, conn=conn
        )
    assert closed, 'Initial close should succeed'

    # Create a changeset referencing the already-closed note
    changeset_id = await _create_changeset(
        user_id=user_id,
        tags={
            'closes:note': str(note_id),
            'closes:note:comment': 'should not apply',
        },
    )

    with exceptions_context(Exceptions06()), auth_context(user):
        await ChangesetService.close(changeset_id)

    # The original close comment must remain unchanged (no new comment added)
    comment = await _get_close_comment(note_id)
    assert comment is not None, 'Close comment must exist'
    assert comment['body'] == 'first close', (
        'Already-closed note must not get new close comment'
    )


async def test_changeset_close_tagged_notes_invalid_ids():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None, 'Test user "user1" must exist'
    user_id = user['id']

    note_id = await _create_note(user_id)
    # Include invalid ids: non-numeric, zero, duplicate — only the valid one counts
    changeset_id = await _create_changeset(
        user_id=user_id,
        tags={
            'closes:note': f'{note_id};abc;0;{note_id}',
            'closes:note:comment': 'ok',
        },
    )

    with exceptions_context(Exceptions06()), auth_context(user):
        await ChangesetService.close(changeset_id)

    # Only the valid note should be closed, exactly once
    note = await _get_note(note_id)
    assert note is not None, 'Note must exist'
    assert note['closed_at'] is not None, 'Valid note must be closed'

    comment = await _get_close_comment(note_id)
    assert comment is not None, 'Close comment must exist'
    assert comment['body'] == 'ok'


async def test_changeset_close_tagged_notes_inactive():
    user = await UserQuery.find_by_display_name(DisplayName('user1'))
    assert user is not None, 'Test user "user1" must exist'
    user_id = user['id']

    note_id = await _create_note(user_id)
    inactive_time = utcnow() - CHANGESET_IDLE_TIMEOUT - timedelta(seconds=1)
    await _create_changeset(
        user_id=user_id,
        tags={'closes:note': str(note_id), 'closes:note:comment': 'auto-closed'},
        updated_at=inactive_time,
    )

    # Force process closes inactive changesets, which should also close tagged notes
    await ChangesetService.force_process()

    note = await _get_note(note_id)
    assert note is not None, 'Note must exist'
    assert note['closed_at'] is not None, (
        'Note must be closed via inactive changeset processing'
    )

    comment = await _get_close_comment(note_id)
    assert comment is not None, 'Close comment must exist'
    assert comment['body'] == 'auto-closed'


async def _create_changeset(
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    closed_at: datetime | None = None,
    *,
    user_id: UserId | None = None,
    tags: dict[str, str] | None = None,
) -> ChangesetId:
    columns = ['user_id', 'tags']
    params: list[Any] = [user_id, tags or {}]

    if created_at is not None:
        columns.append('created_at')
        params.append(created_at)

    if updated_at is not None:
        columns.append('updated_at')
        params.append(updated_at)

    if closed_at is not None:
        columns.append('closed_at')
        params.append(closed_at)

    query = SQL("""
        INSERT INTO changeset (
            {columns}
        )
        VALUES (
            {values}
        )
        RETURNING id
    """).format(
        columns=SQL(',').join(map(Identifier, columns)),
        values=SQL(',').join([SQL('%s')] * len(columns)),
    )

    async with db(True) as conn, await conn.execute(query, params) as r:
        return (await r.fetchone())[0]  # type: ignore


async def _create_note(user_id: UserId, text: str = 'test note') -> NoteId:
    """Create a note with an 'opened' comment and return its id."""
    async with db(True) as conn:
        note_id: NoteId
        note_created_at: datetime
        note_id, note_created_at = await db_insert(
            'note',
            {'point': t'ST_QuantizeCoordinates({Point(0, 0)}, 7)'},
            returning='id, created_at',
            conn=conn,
        )
        await db_insert(
            'note_comment',
            {
                'user_id': user_id,
                'user_ip': None,
                'note_id': note_id,
                'event': 'opened',
                'body': text,
                'created_at': note_created_at,
            },
            conn=conn,
        )
    return note_id


async def _get_note(note_id: NoteId) -> Note | None:
    """Fetch a note by id."""
    return await db_fetchone(Note, t'SELECT * FROM note WHERE id = {note_id}')


async def _get_close_comment(note_id: NoteId) -> NoteComment | None:
    """Fetch the latest 'closed' comment for a note."""
    return await db_fetchone(
        NoteComment,
        t"""
            SELECT * FROM note_comment
            WHERE note_id = {note_id} AND event = 'closed'
            ORDER BY id DESC
            LIMIT 1
        """,
    )
