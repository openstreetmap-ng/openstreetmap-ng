from datetime import timedelta

from sqlalchemy import select

from app.db import db, db_commit
from app.lib.date_utils import utcnow
from app.limits import CHANGESET_EMPTY_DELETE_TIMEOUT, CHANGESET_IDLE_TIMEOUT, CHANGESET_OPEN_TIMEOUT
from app.models.db.changeset import Changeset
from app.services.changeset_service import ChangesetService


async def test_changeset_inactive_close():
    async with db_commit() as session:
        changeset = Changeset(
            user_id=None,
            tags={},
        )
        changeset.updated_at = utcnow() - CHANGESET_IDLE_TIMEOUT - timedelta(seconds=1)
        session.add(changeset)

    # check it exists in the database
    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = (await session.execute(stmt)).scalar_one()
        assert changeset_selected.id == changeset.id
        assert changeset_selected.closed_at is None

    await ChangesetService.force_process()

    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = (await session.execute(stmt)).scalar_one()
        assert changeset_selected.closed_at is not None


async def test_changeset_inactive_open():
    async with db_commit() as session:
        changeset = Changeset(
            user_id=None,
            tags={},
        )
        changeset.updated_at = utcnow() - CHANGESET_IDLE_TIMEOUT + timedelta(minutes=1)
        session.add(changeset)

    # check it exists in the database
    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = (await session.execute(stmt)).scalar_one()
        assert changeset_selected.id == changeset.id
        assert changeset_selected.closed_at is None

    await ChangesetService.force_process()

    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = (await session.execute(stmt)).scalar_one()
        assert changeset_selected.closed_at is None


async def test_changeset_open_timeout_close():
    async with db_commit() as session:
        changeset = Changeset(
            user_id=None,
            tags={},
        )
        changeset.created_at = utcnow() - CHANGESET_OPEN_TIMEOUT - timedelta(seconds=1)
        changeset.updated_at = utcnow()
        session.add(changeset)

    # check it exists in the database
    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = (await session.execute(stmt)).scalar_one()
        assert changeset_selected.id == changeset.id
        assert changeset_selected.closed_at is None

    await ChangesetService.force_process()

    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = (await session.execute(stmt)).scalar_one()
        assert changeset_selected.closed_at is not None


async def test_changeset_open_timeout_open():
    async with db_commit() as session:
        changeset = Changeset(
            user_id=None,
            tags={},
        )
        changeset.created_at = utcnow() - CHANGESET_OPEN_TIMEOUT + timedelta(minutes=1)
        changeset.updated_at = utcnow()
        session.add(changeset)

    # check it exists in the database
    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = (await session.execute(stmt)).scalar_one()
        assert changeset_selected.id == changeset.id
        assert changeset_selected.closed_at is None

    await ChangesetService.force_process()

    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = (await session.execute(stmt)).scalar_one()
        assert changeset_selected.closed_at is None


async def test_changeset_delete_empty():
    async with db_commit() as session:
        changeset = Changeset(
            user_id=None,
            tags={},
        )
        closed_at = utcnow() - CHANGESET_EMPTY_DELETE_TIMEOUT - timedelta(seconds=1)
        changeset.created_at = closed_at
        changeset.updated_at = closed_at
        changeset.closed_at = closed_at
        session.add(changeset)

    # check it exists in the database
    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = (await session.execute(stmt)).scalar_one()
        assert changeset_selected.id == changeset.id
        assert changeset_selected.closed_at is not None

    await ChangesetService.force_process()

    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = await session.scalar(stmt)
        assert changeset_selected is None


async def test_changeset_dont_delete_empty_recent():
    async with db_commit() as session:
        changeset = Changeset(
            user_id=None,
            tags={},
        )
        closed_at = utcnow() - CHANGESET_EMPTY_DELETE_TIMEOUT + timedelta(minutes=1)
        changeset.created_at = closed_at
        changeset.updated_at = closed_at
        changeset.closed_at = closed_at
        session.add(changeset)

    # check it exists in the database
    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = (await session.execute(stmt)).scalar_one()
        assert changeset_selected.id == changeset.id
        assert changeset_selected.closed_at is not None

    await ChangesetService.force_process()

    async with db() as session:
        stmt = select(Changeset).where(Changeset.id == changeset.id)
        changeset_selected = await session.scalar(stmt)
        assert changeset_selected is not None
