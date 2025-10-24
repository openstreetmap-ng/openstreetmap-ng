from datetime import datetime, timedelta
from typing import Any

from psycopg.sql import SQL, Identifier

from app.config import (
    CHANGESET_EMPTY_DELETE_TIMEOUT,
    CHANGESET_IDLE_TIMEOUT,
    CHANGESET_OPEN_TIMEOUT,
)
from app.db import db
from app.lib.date_utils import utcnow
from app.models.types import ChangesetId
from app.queries.changeset_query import ChangesetQuery
from app.services.changeset_service import ChangesetService


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


async def _create_changeset(
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    closed_at: datetime | None = None,
) -> ChangesetId:
    columns: list[str] = ['user_id', 'tags']
    params: list[Any] = [None, {}]

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
