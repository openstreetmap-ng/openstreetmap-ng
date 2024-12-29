import asyncio
import logging
import random
from asyncio import Event, TaskGroup
from contextlib import asynccontextmanager
from time import perf_counter

import cython
from sqlalchemy import and_, delete, func, null, or_, select, text, update
from sqlalchemy.orm import load_only

from app.config import TEST_ENV
from app.db import db, db_commit
from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.exceptions_context import raise_for
from app.lib.retry import retry
from app.lib.testmethod import testmethod
from app.limits import CHANGESET_EMPTY_DELETE_TIMEOUT, CHANGESET_IDLE_TIMEOUT, CHANGESET_OPEN_TIMEOUT
from app.models.db.changeset import Changeset
from app.models.db.user_subscription import UserSubscriptionTarget
from app.services.user_subscription_service import UserSubscriptionService

_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()


class ChangesetService:
    @staticmethod
    async def create(tags: dict[str, str]) -> int:
        """
        Create a new changeset and return its id.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            changeset = Changeset(user_id=user_id, tags=tags)
            session.add(changeset)
        changeset_id = changeset.id
        logging.debug('Created changeset %d by user %d', changeset_id, user_id)
        await UserSubscriptionService.subscribe(UserSubscriptionTarget.changeset, changeset_id)
        return changeset_id

    @staticmethod
    async def update_tags(changeset_id: int, tags: dict[str, str]) -> None:
        """
        Update changeset tags.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            stmt = (
                select(Changeset)
                .options(load_only(Changeset.id, Changeset.user_id, Changeset.closed_at))
                .where(Changeset.id == changeset_id)
                .with_for_update()
            )
            changeset = await session.scalar(stmt)
            if changeset is None:
                raise_for.changeset_not_found(changeset_id)
            if changeset.user_id != user_id:
                raise_for.changeset_access_denied()
            if changeset.closed_at is not None:
                raise_for.changeset_already_closed(changeset_id, changeset.closed_at)
            changeset.tags = tags
        logging.debug('Updated changeset tags for %d by user %d', changeset_id, user_id)

    @staticmethod
    async def close(changeset_id: int) -> None:
        """
        Close a changeset.
        """
        user_id = auth_user(required=True).id
        async with db_commit() as session:
            stmt = (
                select(Changeset)
                .options(load_only(Changeset.id, Changeset.user_id, Changeset.closed_at))
                .where(Changeset.id == changeset_id)
                .with_for_update()
            )
            changeset = await session.scalar(stmt)
            if changeset is None:
                raise_for.changeset_not_found(changeset_id)
            if changeset.user_id != user_id:
                raise_for.changeset_access_denied()
            if changeset.closed_at is not None:
                raise_for.changeset_already_closed(changeset_id, changeset.closed_at)
            changeset.closed_at = func.statement_timestamp()
        logging.debug('Closed changeset %d by user %d', changeset_id, user_id)

    @staticmethod
    @asynccontextmanager
    async def context():
        """
        Context manager for closing idle changesets.
        """
        async with TaskGroup() as tg:
            task = tg.create_task(_process_task())
            yield
            task.cancel()  # avoid "Task was destroyed" warning during tests

    @staticmethod
    @testmethod
    async def force_process():
        """
        Force the changeset processing loop to wake up early, and wait for it to finish.

        This method is only available during testing, and is limited to the current process.
        """
        logging.debug('Requesting changeset processing loop early wakeup')
        _PROCESS_REQUEST_EVENT.set()
        _PROCESS_DONE_EVENT.clear()
        await _PROCESS_DONE_EVENT.wait()


@retry(None)
async def _process_task() -> None:
    test_env: cython.char = bool(TEST_ENV)

    while True:
        async with db() as session:
            # lock is just a random unique number
            acquired: bool = (
                await session.execute(text('SELECT pg_try_advisory_xact_lock(6978403057152160935::bigint)'))
            ).scalar_one()
            if acquired:
                ts = perf_counter()
                async with TaskGroup() as tg:
                    tg.create_task(_close_inactive())
                    tg.create_task(_delete_empty())
                tt = perf_counter() - ts
                # on success, sleep ~1min
                delay = random.uniform(50, 70) - tt  # noqa: S311
            else:
                # on failure, sleep ~1h
                delay = random.uniform(1800, 5400)  # noqa: S311

        if test_env:
            _PROCESS_DONE_EVENT.set()
            async with TaskGroup() as tg:
                event_task = tg.create_task(_PROCESS_REQUEST_EVENT.wait())
                await asyncio.wait((event_task,), timeout=delay)
                if event_task.done():
                    logging.debug('Changeset processing loop early wakeup')
                    _PROCESS_REQUEST_EVENT.clear()
                else:
                    event_task.cancel()
        else:
            await asyncio.sleep(delay)


async def _close_inactive() -> None:
    """
    Close all inactive changesets.
    """
    async with db_commit() as session:
        now = utcnow()
        stmt = (
            update(Changeset)
            .where(
                Changeset.closed_at == null(),
                or_(
                    Changeset.updated_at < now - CHANGESET_IDLE_TIMEOUT,
                    and_(
                        # reference updated_at to use the index
                        Changeset.updated_at >= now - CHANGESET_IDLE_TIMEOUT,
                        Changeset.created_at < now - CHANGESET_OPEN_TIMEOUT,
                    ),
                ),
            )
            .values({Changeset.closed_at: now})
            .inline()
        )
        result = await session.execute(stmt)
        if result.rowcount:
            logging.debug('Closed %d inactive changesets', result.rowcount)


async def _delete_empty() -> None:
    """
    Delete empty changesets after a timeout.
    """
    async with db_commit() as session:
        now = utcnow()
        stmt = delete(Changeset).where(
            Changeset.closed_at != null(),
            Changeset.closed_at < now - CHANGESET_EMPTY_DELETE_TIMEOUT,
            Changeset.size == 0,
        )
        result = await session.execute(stmt)
        if result.rowcount:
            logging.debug('Deleted %d empty changesets', result.rowcount)
