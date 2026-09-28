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
from app.db import (
    db,
    db_delete,
    db_fetchcol,
    db_fetchrow,
    db_fetchval,
    db_insert,
    db_lock,
    db_update,
)
from app.exceptions.context import raise_for
from app.lib.audit import audit
from app.lib.auth.context import auth_user
from app.lib.http.retry import retry
from app.lib.telemetry.sentry import (
    SENTRY_CHANGESET_MANAGEMENT_MONITOR,
    SENTRY_CHANGESET_MANAGEMENT_MONITOR_SLUG,
)
from app.lib.telemetry.testmethod import testmethod
from app.lib.text.translation import t, translation_context
from app.models.db.changeset_comment import (
    ChangesetComment,
    changeset_comments_resolve_rich_text,
)
from app.models.proto.note_types import GetCommentsResponse_Comment_Event
from app.models.types import ChangesetCommentId, ChangesetId, DisplayName, NoteId, UserId
from app.queries.changeset_query import ChangesetQuery
from app.queries.note_query import NoteQuery
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

        async with db(True) as conn:
            row = await db_insert(
                'changeset',
                {'user_id': user_id, 'tags': tags},
                returning='id',
                conn=conn,
            )
            changeset_id: ChangesetId = row[0]

            await audit('create_changeset', conn, extra={'id': changeset_id})

        await UserSubscriptionService.subscribe('changeset', changeset_id)
        return changeset_id

    @staticmethod
    async def update_tags(changeset_id: ChangesetId, tags: dict[str, str]):
        """Update changeset tags."""
        user_id = auth_user(required=True)['id']

        async with db(True) as conn:
            row = await db_fetchrow(
                t"""
                    SELECT user_id, closed_at
                    FROM changeset
                    WHERE id = {changeset_id}
                """,
                for_update=True,
                conn=conn,
            )
            if row is None:
                raise_for.changeset_not_found(changeset_id)

            changeset_user_id: UserId
            closed_at: datetime | None
            changeset_user_id, closed_at = row

            if changeset_user_id != user_id:
                raise_for.changeset_access_denied()
            if closed_at is not None:
                raise_for.changeset_already_closed(changeset_id, closed_at)

            await db_update(
                'changeset',
                {'tags': tags, 'updated_at': t'DEFAULT'},
                where={'id': changeset_id},
                conn=conn,
            )
            await audit('update_changeset', conn, extra={'id': changeset_id})

    @staticmethod
    async def close(changeset_id: ChangesetId):
        """Close a changeset."""
        user_id = auth_user(required=True)['id']
        note_closures: list[tuple[NoteId, str]] = []

        async with db(True) as conn:
            row = await db_fetchrow(
                t"""
                    SELECT user_id, closed_at, tags
                    FROM changeset
                    WHERE id = {changeset_id}
                """,
                for_update=True,
                conn=conn,
            )
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

            await db_update(
                'changeset',
                {
                    'closed_at': t'statement_timestamp()',
                    'updated_at': t'DEFAULT',
                },
                where={'id': changeset_id},
                conn=conn,
            )
            await audit('close_changeset', conn, extra={'id': changeset_id})
            note_closures = await _get_note_closures_from_changeset_tags(tags)

        for note_id, text in note_closures:
            await NoteService.comment(
                note_id,
                text,
                GetCommentsResponse_Comment_Event.Value('closed'),
            )

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

        async with db(True) as conn:
            exists = await db_fetchval(
                int,
                t'SELECT 1 FROM changeset WHERE id = {changeset_id} FOR SHARE',
                conn=conn,
            )
            if exists is None:
                raise_for.changeset_not_found(changeset_id)

            row = await db_insert(
                'changeset_comment',
                {'user_id': user_id, 'changeset_id': changeset_id, 'body': text},
                returning='id, created_at',
                conn=conn,
            )
            comment_id: ChangesetCommentId
            created_at: datetime
            comment_id, created_at = row

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
        row = await db_delete(
            'changeset_comment',
            where={'id': comment_id},
            returning='changeset_id',
            assert_returning=False,
        )
        if row is None:
            raise_for.changeset_comment_not_found(comment_id)

        changeset_id: ChangesetId = row[0]
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
    rowcount = await db_update(
        'changeset',
        {'closed_at': t'statement_timestamp()', 'updated_at': t'DEFAULT'},
        where=t"""closed_at IS NULL AND (
                updated_at < statement_timestamp() - {CHANGESET_IDLE_TIMEOUT} OR
                (updated_at >= statement_timestamp() - {CHANGESET_IDLE_TIMEOUT} AND
                created_at < statement_timestamp() - {CHANGESET_OPEN_TIMEOUT})
            )""",
    )

    if rowcount:
        logging.debug('Closed %d inactive changesets', rowcount)


async def _get_note_closures_from_changeset_tags(
    tags: dict[str, str],
) -> list[tuple[NoteId, str]]:
    raw_ids = tags.get('closes:note')
    if not raw_ids:
        return []

    default_comment = tags.get('closes:note:comment') or tags.get('comment') or ''
    per_note_comments: dict[NoteId, str] = {}
    note_ids: list[NoteId] = []
    seen = set[NoteId]()

    for key, value in tags.items():
        if not (key.startswith('closes:note:') and key.endswith(':comment')):
            continue
        raw_note_id = key[len('closes:note:') : -len(':comment')]
        if raw_note_id == 'comment' or not raw_note_id.isdigit():
            continue
        per_note_comments[NoteId(int(raw_note_id))] = value

    for raw_note_id in raw_ids.split(';'):
        raw_note_id = raw_note_id.strip()
        if not raw_note_id or not raw_note_id.isdigit():
            continue
        note_id = NoteId(int(raw_note_id))
        if note_id in seen:
            continue
        seen.add(note_id)
        note_ids.append(note_id)

    if not note_ids:
        return []

    notes = await NoteQuery.find(note_ids=note_ids, limit=len(note_ids))
    available = {
        note['id']
        for note in notes
        if note['closed_at'] is None and note['hidden_at'] is None
    }

    return [
        (note_id, per_note_comments.get(note_id, default_comment))
        for note_id in note_ids
        if note_id in available
    ]


async def _delete_empty():
    """Delete empty changesets after a timeout."""
    async with db(True) as conn:
        changeset_ids = await db_fetchcol(
            ChangesetId,
            t"""
                SELECT id FROM changeset
                WHERE closed_at IS NOT NULL
                  AND closed_at < statement_timestamp() - {CHANGESET_EMPTY_DELETE_TIMEOUT}
                  AND size = 0
            """,
            conn=conn,
        )
        if not changeset_ids:
            return

        await db_delete(
            'changeset',
            where=t'id = ANY({changeset_ids})',
            conn=conn,
        )
        await db_delete(
            'changeset_bounds',
            where=t'changeset_id = ANY({changeset_ids})',
            conn=conn,
        )
        await db_delete(
            'changeset_comment',
            where=t'changeset_id = ANY({changeset_ids})',
            conn=conn,
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
