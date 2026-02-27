import asyncio
import logging
from asyncio import Event, TaskGroup
from contextlib import asynccontextmanager
from datetime import datetime
from random import uniform
from time import monotonic

from sentry_sdk.api import start_transaction

from app.config import (
    CHANGESET_EMPTY_DELETE_TIMEOUT,
    CHANGESET_IDLE_TIMEOUT,
    CHANGESET_OPEN_TIMEOUT,
)
from app.db import db, db_lock
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.retry import retry
from app.lib.sentry import (
    SENTRY_CHANGESET_MANAGEMENT_MONITOR,
    SENTRY_CHANGESET_MANAGEMENT_MONITOR_SLUG,
)
from app.lib.testmethod import testmethod
from app.models.db.changeset import ChangesetInit
from app.models.types import ChangesetId, NoteId, UserId
from app.services.audit_service import audit
from app.services.user_subscription_service import UserSubscriptionService

_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()


class ChangesetService:
    @staticmethod
    async def create(tags: dict[str, str]) -> ChangesetId:
        """Create a new changeset and return its id."""
        user_id = auth_user(required=True)['id']

        changeset_init: ChangesetInit = {
            'user_id': user_id,
            'tags': tags,
        }

        async with db(True) as conn:
            async with await conn.execute(
                """
                INSERT INTO changeset (
                    user_id, tags
                )
                VALUES (
                    %(user_id)s, %(tags)s
                )
                RETURNING id
                """,
                changeset_init,
            ) as r:
                changeset_id: ChangesetId = (await r.fetchone())[0]  # type: ignore

            await audit('create_changeset', conn, extra={'id': changeset_id})

        await UserSubscriptionService.subscribe('changeset', changeset_id)
        return changeset_id

    @staticmethod
    async def update_tags(changeset_id: ChangesetId, tags: dict[str, str]) -> None:
        """Update changeset tags."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT user_id, closed_at
                FROM changeset
                WHERE id = %s
                FOR UPDATE
                """,
                (changeset_id,),
            ) as r:
                row = await r.fetchone()
                if row is None:
                    raise_for.changeset_not_found(changeset_id)

                changeset_user_id: UserId
                closed_at: datetime | None
                changeset_user_id, closed_at = row

                if changeset_user_id != user_id:
                    raise_for.changeset_access_denied()
                if closed_at is not None:
                    raise_for.changeset_already_closed(changeset_id, closed_at)

            await conn.execute(
                """
                UPDATE changeset
                SET tags = %s, updated_at = DEFAULT
                WHERE id = %s
                """,
                (tags, changeset_id),
            )
            await audit('update_changeset', conn, extra={'id': changeset_id})

    @staticmethod
    async def close(changeset_id: ChangesetId) -> None:
        """Close a changeset."""
        user_id = auth_user(required=True)['id']
        tags: dict[str, str] | None = None

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT user_id, closed_at, tags
                FROM changeset
                WHERE id = %s
                FOR UPDATE
                """,
                (changeset_id,),
            ) as r:
                row = await r.fetchone()
                if row is None:
                    raise_for.changeset_not_found(changeset_id)

                changeset_user_id: UserId
                closed_at: datetime | None
                changeset_user_id, closed_at, tags = row

                if changeset_user_id != user_id:
                    raise_for.changeset_access_denied()
                if closed_at is not None:
                    raise_for.changeset_already_closed(changeset_id, closed_at)

            await conn.execute(
                """
                UPDATE changeset
                SET closed_at = statement_timestamp(), updated_at = DEFAULT
                WHERE id = %s
                """,
                (changeset_id,),
            )
            await audit('close_changeset', conn, extra={'id': changeset_id})

        # Process automatic note closing
        if tags:
            await _close_notes_from_tags(tags)

    @staticmethod
    @asynccontextmanager
    async def context():
        """Context manager for closing idle changesets."""
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


async def _close_notes_from_tags(tags: dict[str, str]) -> None:
    """
    Close notes listed in the closes:note tag.

    Tag format:
    - closes:note: IDs separated by ;
    - closes:note:comment: default comment for all notes
    - closes:note:ID:comment: individual note comment override
    """
    from app.services.note_service import NoteService

    closes_note = tags.get('closes:note')
    if not closes_note:
        return

    # Parse note IDs
    note_ids: list[NoteId] = []
    for part in closes_note.split(';'):
        part = part.strip()
        if part.isdigit():
            note_ids.append(int(part))

    if not note_ids:
        return

    # Get default comment from changeset comment tag or closes:note:comment
    default_comment = tags.get('closes:note:comment', tags.get('comment', ''))

    # Close each note
    for note_id in note_ids:
        # Check for individual note comment override
        comment = tags.get(f'closes:note:{note_id}:comment', default_comment)

        try:
            await NoteService.comment(note_id, comment, 'closed')
            logging.debug('Closed note %d via closes:note tag', note_id)
        except Exception:
            # Note may already be closed or not exist - continue with others
            logging.debug('Failed to close note %d (may already be closed)', note_id)


@retry(None)
async def _process_task() -> None:
    async def sleep(delay: float) -> None:
        if delay > 0:
            try:
                await asyncio.wait_for(_PROCESS_REQUEST_EVENT.wait(), timeout=delay)
            except TimeoutError:
                pass

    while True:
        async with db_lock(6978403057152160935) as acquired:
            if acquired:
                _PROCESS_REQUEST_EVENT.clear()

                ts = monotonic()
                with (
                    SENTRY_CHANGESET_MANAGEMENT_MONITOR,
                    start_transaction(
                        op='task', name=SENTRY_CHANGESET_MANAGEMENT_MONITOR_SLUG
                    ),
                ):
                    await _close_inactive()
                    await _delete_empty()
                tt = monotonic() - ts

                if not _PROCESS_REQUEST_EVENT.is_set():
                    _PROCESS_DONE_EVENT.set()

                # on success, sleep ~1min
                await sleep(uniform(50, 70) - tt)
            else:
                # on failure, sleep ~1h
                await sleep(uniform(0.5 * 3600, 1.5 * 3600))


async def _close_inactive() -> None:
    """Close all inactive changesets."""
    async with db(True) as conn:
        result = await conn.execute(
            """
            UPDATE changeset
            SET closed_at = statement_timestamp(), updated_at = DEFAULT
            WHERE closed_at IS NULL AND (
                updated_at < statement_timestamp() - %s OR
                (updated_at >= statement_timestamp() - %s AND
                created_at < statement_timestamp() - %s)
            )
            """,
            (CHANGESET_IDLE_TIMEOUT, CHANGESET_IDLE_TIMEOUT, CHANGESET_OPEN_TIMEOUT),
        )

        if result.rowcount:
            logging.debug('Closed %d inactive changesets', result.rowcount)


async def _delete_empty() -> None:
    """Delete empty changesets after a timeout."""
    async with db(True) as conn:
        async with await conn.execute(
            """
            SELECT id FROM changeset
            WHERE closed_at IS NOT NULL
              AND closed_at < statement_timestamp() - %s
              AND size = 0
            """,
            (CHANGESET_EMPTY_DELETE_TIMEOUT,),
        ) as r:
            changeset_ids = [c for (c,) in await r.fetchall()]
            if not changeset_ids:
                return

        await conn.execute(
            """
            DELETE FROM changeset
            WHERE id = ANY(%s)
            """,
            (changeset_ids,),
        )
        await conn.execute(
            """
            DELETE FROM changeset_bounds
            WHERE changeset_id = ANY(%s)
            """,
            (changeset_ids,),
        )
        await conn.execute(
            """
            DELETE FROM changeset_comment
            WHERE changeset_id = ANY(%s)
            """,
            (changeset_ids,),
        )

        logging.debug('Deleted %d empty changesets', len(changeset_ids))
