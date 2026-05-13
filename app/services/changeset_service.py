import asyncio
import logging
from asyncio import Event, TaskGroup
from contextlib import asynccontextmanager
from datetime import datetime
from random import uniform
from time import monotonic
from typing import Any

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
from app.models.types import ChangesetId, NoteCommentId, NoteId, UserId
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
    async def update_tags(changeset_id: ChangesetId, tags: dict[str, str]):
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
    async def close(changeset_id: ChangesetId):
        """Close a changeset."""
        user_id = auth_user(required=True)['id']

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
                tags: dict[str, str]
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
            await _close_notes_tagged_by_changeset(conn, tags, user_id)

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


def _parse_closes_note_ids(tags: dict[str, str]) -> list[NoteId]:
    """Parse semicolon-separated numeric note IDs from the closes:note tag."""
    raw_note_ids = tags.get('closes:note')
    if not raw_note_ids:
        return []

    note_ids: list[NoteId] = []
    for raw_note_id in raw_note_ids.split(';'):
        raw_note_id = raw_note_id.strip()
        if raw_note_id.isdigit():
            note_ids.append(NoteId(int(raw_note_id)))
    return note_ids


def _note_close_comment(tags: dict[str, str], note_id: NoteId) -> str:
    """Return per-note override, all-note override, changeset comment, or empty."""
    return (
        tags.get(f'closes:note:{note_id}:comment')
        or tags.get('closes:note:comment')
        or tags.get('comment')
        or ''
    )


async def _close_notes_tagged_by_changeset(
    conn: Any, tags: dict[str, str], user_id: UserId | None
) -> None:
    """Close notes referenced by closes:note tags when a changeset closes."""
    note_ids = _parse_closes_note_ids(tags)
    if not note_ids:
        return

    for note_id in note_ids:
        body = _note_close_comment(tags, note_id)
        async with await conn.execute(
            """
            WITH updated_note AS (
                UPDATE note
                SET closed_at = statement_timestamp(), updated_at = statement_timestamp()
                WHERE id = %(note_id)s
                  AND closed_at IS NULL
                RETURNING id, updated_at
            ), inserted_comment AS (
                INSERT INTO note_comment (
                    user_id, user_ip, note_id, event, body, created_at
                )
                SELECT %(user_id)s, NULL, id, 'closed', %(body)s, updated_at
                FROM updated_note
                RETURNING id, note_id
            )
            SELECT id, note_id FROM inserted_comment
            """,
            {'note_id': note_id, 'user_id': user_id, 'body': body},
        ) as r:
            row = await r.fetchone()

        # If the note does not exist or is already closed, the bounty asks us to do nothing.
        if row is None:
            continue

        comment_id: NoteCommentId
        closed_note_id: NoteId
        comment_id, closed_note_id = row

        if body:
            await audit(
                'create_note_comment',
                conn,
                extra={'id': comment_id, 'note': closed_note_id},
            )
        await audit(
            'update_note_status',
            conn,
            extra={'id': closed_note_id, 'event': 'closed'},
        )


@retry(None)
async def _process_task():
    async def sleep(delay: float):
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


async def _close_inactive():
    """Close all inactive changesets."""
    async with db(True) as conn:
        async with await conn.execute(
            """
            UPDATE changeset
            SET closed_at = statement_timestamp(), updated_at = DEFAULT
            WHERE closed_at IS NULL AND (
                updated_at < statement_timestamp() - %s OR
                (updated_at >= statement_timestamp() - %s AND
                created_at < statement_timestamp() - %s)
            )
            RETURNING id, tags, user_id
            """,
            (CHANGESET_IDLE_TIMEOUT, CHANGESET_IDLE_TIMEOUT, CHANGESET_OPEN_TIMEOUT),
        ) as r:
            closed_changesets = await r.fetchall()

        if closed_changesets:
            logging.debug('Closed %d inactive changesets', len(closed_changesets))
            for _, tags, user_id in closed_changesets:
                await _close_notes_tagged_by_changeset(conn, tags, user_id)


async def _delete_empty():
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
