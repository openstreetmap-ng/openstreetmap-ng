import asyncio
import logging
from asyncio import Event, TaskGroup
from contextlib import asynccontextmanager
from datetime import datetime
from random import uniform
from time import monotonic

import cython
from sentry_sdk.api import start_transaction

from app.config import (
    CHANGESET_EMPTY_DELETE_TIMEOUT,
    CHANGESET_IDLE_TIMEOUT,
    CHANGESET_OPEN_TIMEOUT,
)
from app.db import db, db_lock
from app.exceptions.context import raise_for
from app.lib.audit import audit
from app.lib.auth.context import auth_context, auth_scopes, auth_user
from app.lib.http.retry import retry
from app.lib.telemetry.sentry import (
    SENTRY_CHANGESET_MANAGEMENT_MONITOR,
    SENTRY_CHANGESET_MANAGEMENT_MONITOR_SLUG,
)
from app.lib.telemetry.testmethod import testmethod
from app.lib.text.translation import t, translation_context
from app.models.db.changeset import ChangesetInit
from app.models.db.changeset_comment import (
    ChangesetComment,
    ChangesetCommentInit,
    changeset_comments_resolve_rich_text,
)
from app.models.types import ChangesetCommentId, ChangesetId, DisplayName, NoteId, UserId
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.email_service import EmailService
from app.services.note_service import NoteService
from app.services.user_subscription_service import UserSubscriptionService

_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()


class ChangesetService:
    @staticmethod
    async def create(tags: dict[str, str]) -> ChangesetId:
        """Create a new changeset and return its id."""
        user_id = auth_user(required=True)['id']
        _require_note_write_scope(tags)

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
                _require_note_write_scope(tags)

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
        tags: dict[str, str]

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

                changeset_user_id: UserId | None
                closed_at: datetime | None
                tags: dict[str, str]
                changeset_user_id, closed_at, tags = row

                if changeset_user_id != user_id:
                    raise_for.changeset_access_denied()
                if closed_at is not None:
                    raise_for.changeset_already_closed(changeset_id, closed_at)
                _require_note_write_scope(tags)

            await conn.execute(
                """
                UPDATE changeset
                SET closed_at = statement_timestamp(), updated_at = DEFAULT
                WHERE id = %s
                """,
                (changeset_id,),
            )
            await audit('close_changeset', conn, extra={'id': changeset_id})

        if _parse_closes_note_ids(tags):
            await _close_tagged_notes(tags)

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


# === Changeset Comments ===


class ChangesetCommentService:
    @staticmethod
    async def comment(changeset_id: ChangesetId, text: str):
        """Comment on a changeset."""
        user = auth_user(required=True)
        user_id = user['id']

        comment_init: ChangesetCommentInit = {
            'user_id': user_id,
            'changeset_id': changeset_id,
            'body': text,
        }

        async with db(True) as conn:
            async with await conn.execute(
                """
                SELECT 1 FROM changeset
                WHERE id = %s
                FOR SHARE
                """,
                (changeset_id,),
            ) as r:
                if await r.fetchone() is None:
                    raise_for.changeset_not_found(changeset_id)

            async with await conn.execute(
                """
                INSERT INTO changeset_comment (
                    user_id, changeset_id, body
                )
                VALUES (
                    %(user_id)s, %(changeset_id)s, %(body)s
                )
                RETURNING id, created_at
                """,
                comment_init,
            ) as r:
                comment_id: ChangesetCommentId
                created_at: datetime
                comment_id, created_at = await r.fetchone()  # type: ignore

            await audit(
                'create_changeset_comment',
                conn,
                extra={'id': comment_id, 'changeset': changeset_id},
            )

        comment: ChangesetComment = {
            'id': comment_id,
            'user_id': user_id,
            'changeset_id': changeset_id,
            'body': text,
            'body_rich_hash': None,
            'created_at': created_at,
            'user': user,  # type: ignore
        }

        async with TaskGroup() as tg:
            tg.create_task(_send_activity_email(comment))
            tg.create_task(UserSubscriptionService.subscribe('changeset', changeset_id))

    # TODO: hide, audit
    @staticmethod
    async def delete_comment_unsafe(comment_id: ChangesetCommentId):
        """Delete any changeset comment. Returns the parent changeset id."""
        async with (
            db(True) as conn,
            await conn.execute(
                """
                DELETE FROM changeset_comment
                WHERE id = %s
                RETURNING changeset_id
                """,
                (comment_id,),
            ) as r,
        ):
            result = await r.fetchone()
            if result is None:
                raise_for.changeset_comment_not_found(comment_id)

            changeset_id: ChangesetId = result[0]
            logging.debug(
                'Deleted changeset comment %d from changeset %d',
                comment_id,
                changeset_id,
            )
            return changeset_id


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
            RETURNING user_id, tags
            """,
            (CHANGESET_IDLE_TIMEOUT, CHANGESET_IDLE_TIMEOUT, CHANGESET_OPEN_TIMEOUT),
        ) as r:
            rows: list[tuple[UserId | None, dict[str, str]]] = await r.fetchall()  # type: ignore

        if rows:
            logging.debug('Closed %d inactive changesets', len(rows))
            await _close_inactive_tagged_notes(rows)


async def _close_inactive_tagged_notes(
    rows: list[tuple[UserId | None, dict[str, str]]],
):
    for user_id, tags in rows:
        if user_id is None or not _parse_closes_note_ids(tags):
            continue

        user = await UserQuery.find_by_id(user_id)
        if user is None:
            continue

        with auth_context(user, frozenset(('write_notes',))):
            await _close_tagged_notes(tags)


async def _close_tagged_notes(tags: dict[str, str]):
    """Close notes referenced by the changeset's closes:note tags."""
    for note_id in _parse_closes_note_ids(tags):
        body = _get_note_close_body(note_id, tags)
        await NoteService.comment(
            note_id,
            body,
            'closed',
            ignore_closed_or_missing=True,
        )


def _require_note_write_scope(tags: dict[str, str]):
    if not tags.get('closes:note'):
        return

    scopes = auth_scopes()
    if 'web_user' not in scopes and 'write_notes' not in scopes:
        raise_for.insufficient_scopes(['write_notes'])


def _parse_closes_note_ids(tags: dict[str, str]) -> list[NoteId]:
    value = tags.get('closes:note')
    if value is None:
        return []

    note_ids: list[NoteId] = []
    seen: set[int] = set()
    for item in value.split(';'):
        item = item.strip()
        if not item.isdecimal():
            continue

        note_id = int(item)
        if note_id <= 0 or note_id in seen:
            continue

        seen.add(note_id)
        note_ids.append(NoteId(note_id))

    return note_ids


def _get_note_close_body(note_id: NoteId, tags: dict[str, str]) -> str:
    note_comment_key = f'closes:note:{int(note_id)}:comment'
    if note_comment_key in tags:
        return tags[note_comment_key]
    if 'closes:note:comment' in tags:
        return tags['closes:note:comment']
    return tags.get('comment', '')


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


async def _send_activity_email(comment: ChangesetComment):
    changeset_id = comment['changeset_id']

    async def changeset_task():
        changeset = await ChangesetQuery.find_by_id(changeset_id)
        assert changeset is not None, f'Parent changeset {changeset_id} must exist'
        await UserQuery.resolve_users([changeset])
        return changeset

    async with TaskGroup() as tg:
        tg.create_task(changeset_comments_resolve_rich_text([comment]))
        changeset_t = tg.create_task(changeset_task())
        users = await UserSubscriptionQuery.get_subscribed_users(
            'changeset', changeset_id
        )
        if not users:
            return

    changeset = changeset_t.result()
    changeset_user_id: cython.size_t = changeset['user_id'] or 0
    changeset_comment_str = changeset.get('tags', {}).get('comment')

    comment_user = comment['user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    comment_user_id: cython.size_t = comment_user['id']
    comment_user_name = comment_user['display_name']
    ref = f'changeset-{changeset["id"]}'

    async with TaskGroup() as tg:
        for subscribed_user in users:
            subscribed_user_id: cython.size_t = subscribed_user['id']
            if subscribed_user_id == comment_user_id:
                continue

            with translation_context(subscribed_user['language']):
                is_changeset_owner: cython.bint = (
                    subscribed_user_id == changeset_user_id
                )
                subject = _get_activity_email_subject(
                    comment_user_name, is_changeset_owner
                )

            tg.create_task(
                EmailService.schedule(
                    source=None,
                    from_user_id=None,
                    to_user=subscribed_user,
                    subject=subject,
                    template_name='email/changeset-comment',
                    template_data={
                        'changeset': changeset,
                        'changeset_comment_str': changeset_comment_str,
                        'comment': comment,
                        'is_changeset_owner': is_changeset_owner,
                    },
                    ref=ref,
                )
            )


@cython.cfunc
def _get_activity_email_subject(
    comment_user_name: DisplayName,
    is_changeset_owner: cython.bint,
):
    return t(
        'user_mailer.changeset_comment_notification.commented.subject_own'
        if is_changeset_owner
        else 'user_mailer.changeset_comment_notification.commented.subject other',
        commenter=comment_user_name,
    )
