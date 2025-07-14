import logging
from asyncio import TaskGroup
from datetime import datetime
from typing import Any

import cython
from httpx import HTTPError
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable
from shapely import Point, get_coordinates

from app.db import db
from app.lib.auth_context import auth_user, auth_user_scopes
from app.lib.exceptions_context import raise_for
from app.lib.translation import t, translation_context
from app.middlewares.request_context_middleware import get_request_ip
from app.models.db.note import Note, NoteInit
from app.models.db.note_comment import (
    NoteComment,
    NoteCommentInit,
    NoteEvent,
    note_comments_resolve_rich_text,
)
from app.models.db.user import user_is_moderator
from app.models.types import DisplayName, NoteCommentId, NoteId
from app.queries.nominatim_query import NominatimQuery
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.email_service import EmailService
from app.services.user_subscription_service import UserSubscriptionService
from app.validators.geometry import validate_geometry


class NoteService:
    @staticmethod
    async def create(lon: float, lat: float, text: str) -> NoteId:
        """Create a note and return its id."""
        point = validate_geometry(Point(lon, lat))

        user, scopes = auth_user_scopes()
        if user is not None:
            # Prevent OAuth to create user-authorized note
            if 'web_user' not in scopes and 'write_notes' not in scopes:
                raise_for.insufficient_scopes(['write_notes'])
            user_id = user['id']
            user_ip = None
        else:
            user_id = None
            user_ip = get_request_ip()

        async with db(True) as conn:
            note_init: NoteInit = {
                'point': point,
            }

            async with await conn.execute(
                """
                INSERT INTO note (
                    point
                )
                VALUES (
                    ST_QuantizeCoordinates(%(point)s, 5)
                )
                RETURNING id, created_at
                """,
                note_init,
            ) as r:
                note_id: NoteId
                note_created_at: datetime
                note_id, note_created_at = await r.fetchone()  # type: ignore

            comment_init: NoteCommentInit = {
                'user_id': user_id,
                'user_ip': user_ip,
                'note_id': note_id,
                'event': 'opened',
                'body': text,
            }

            await conn.execute(
                """
                INSERT INTO note_comment (
                    user_id, user_ip, note_id, event, body, created_at
                )
                VALUES (
                    %(user_id)s, %(user_ip)s, %(note_id)s, %(event)s, %(body)s, %(created_at)s
                )
                RETURNING created_at
                """,
                {
                    **comment_init,
                    'created_at': note_created_at,
                },
            )

        if user_id is not None:
            logging.debug('Created note %d by user %d', note_id, user_id)
            await UserSubscriptionService.subscribe('note', note_id)
        else:
            logging.debug('Created note %d by anonymous user', note_id)

        return note_id

    @staticmethod
    async def comment(note_id: NoteId, text: str, event: NoteEvent) -> None:
        """Comment on a note."""
        user = auth_user(required=True)
        user_id = user['id']
        send_activity_email: cython.bint = False

        conditions: list[Composable] = [SQL('id = %s')]
        params: list[Any] = [note_id]

        # Only show hidden notes to moderators
        if not user_is_moderator(user):
            conditions.append(SQL('hidden_at IS NULL'))

        query = SQL("""
            SELECT * FROM note
            WHERE {conditions}
            FOR UPDATE
        """).format(conditions=SQL(' AND ').join(conditions))

        async with db(True) as conn:
            async with await conn.cursor(row_factory=dict_row).execute(
                query, params
            ) as r:
                note: Note | None = await r.fetchone()  # type: ignore
                if note is None:
                    raise_for.note_not_found(note_id)

            del conditions
            update: list[Composable] = []
            params.clear()

            if event == 'closed':
                if note['closed_at'] is not None:
                    raise_for.note_closed(note_id, note['closed_at'])
                update.append(SQL('closed_at = statement_timestamp()'))
                send_activity_email = True

            elif event == 'reopened':
                # Unhide
                if note['hidden_at'] is not None:
                    update.append(SQL('hidden_at = NULL'))
                # Reopen
                else:
                    if note['closed_at'] is None:
                        raise_for.note_open(note_id)
                    update.append(SQL('closed_at = NULL'))
                    send_activity_email = True

            elif event == 'commented':
                if note['closed_at'] is not None:
                    raise_for.note_closed(note_id, note['closed_at'])
                send_activity_email = True

            elif event == 'hidden':
                if not user_is_moderator(user):
                    raise_for.insufficient_scopes(['role_moderator'])
                update.append(SQL('hidden_at = statement_timestamp()'))

            else:
                raise NotImplementedError(f'Unsupported note event {event!r}')

            comment_init: NoteCommentInit = {
                'user_id': user_id,
                'user_ip': None,
                'note_id': note_id,
                'event': event,
                'body': text,
            }

            async with await conn.execute(
                """
                INSERT INTO note_comment (
                    user_id, user_ip, note_id, event, body
                )
                VALUES (
                    %(user_id)s, %(user_ip)s, %(note_id)s, %(event)s, %(body)s
                )
                RETURNING id, created_at
                """,
                comment_init,
            ) as r:
                comment_id: NoteCommentId
                created_at: datetime
                comment_id, created_at = await r.fetchone()  # type: ignore

            # Update the note's updated_at to match the comment's created_at
            update.append(SQL('updated_at = %s'))
            params.append(created_at)

            query = SQL("""
                UPDATE note
                SET {}
                WHERE id = %s
            """).format(SQL(',').join(update))
            params.append(note_id)
            await conn.execute(query, params)

        logging.debug('Created note comment on note %d by user %d', note_id, user_id)

        comment: NoteComment = {
            'id': comment_id,
            'user_id': user_id,
            'user_ip': None,
            'note_id': note_id,
            'event': event,
            'body': text,
            'body_rich_hash': None,
            'created_at': created_at,
            'user': user,  # type: ignore
        }

        async with TaskGroup() as tg:
            if send_activity_email:
                tg.create_task(_send_activity_email(note, comment))
            tg.create_task(UserSubscriptionService.subscribe('note', note_id))


async def _send_activity_email(note: Note, comment: NoteComment) -> None:
    async def place_task():
        try:
            # Reverse geocode the note point
            result = await NominatimQuery.reverse(note['point'])
            if result is not None:
                return result.display_name
        except HTTPError:
            pass

        x, y = get_coordinates(note['point'])[0].tolist()
        return f'{y:.5f}, {x:.5f}'

    async with TaskGroup() as tg:
        tg.create_task(note_comments_resolve_rich_text([comment]))
        place_t = tg.create_task(place_task())

        # Fetch the first comment (which is the opening comment)
        first_comments_t = tg.create_task(
            NoteCommentQuery.get_comments_page(
                note['id'],
                page=1,
                num_items=1,
                skip_header=False,
            )
        )

        users = await UserSubscriptionQuery.get_subscribed_users(
            'note', comment['note_id']
        )
        if not users:
            return

    place = place_t.result()
    first_comments = first_comments_t.result()
    assert first_comments, 'Note must have at least one comment'
    first_comment_user_id: cython.longlong = first_comments[0]['user_id'] or 0

    assert comment['user_id'] is not None, (
        'Anonymous note comments are no longer supported'
    )
    comment_user = comment['user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    comment_user_id: cython.longlong = comment_user['id']
    comment_user_name = comment_user['display_name']
    comment_event = comment['event']
    ref = f'note-{note["id"]}'

    async with TaskGroup() as tg:
        for subscribed_user in users:
            subscribed_user_id: cython.longlong = subscribed_user['id']
            if subscribed_user_id == comment_user_id:
                continue

            with translation_context(subscribed_user['language']):
                is_note_owner: cython.bint = subscribed_user_id == first_comment_user_id
                subject = _get_activity_email_subject(
                    comment_user_name, comment_event, is_note_owner
                )

            tg.create_task(
                EmailService.schedule(
                    source=None,
                    from_user_id=None,
                    to_user=subscribed_user,
                    subject=subject,
                    template_name='email/note-activity',
                    template_data={
                        'comment': comment,
                        'is_note_owner': is_note_owner,
                        'place': place,
                    },
                    ref=ref,
                )
            )


@cython.cfunc
def _get_activity_email_subject(
    comment_user_name: DisplayName,
    event: NoteEvent,
    is_note_owner: cython.bint,
) -> str:
    if event == 'commented':
        if is_note_owner:
            return t(
                'user_mailer.note_comment_notification.commented.subject_own',
                commenter=comment_user_name,
            )
        else:
            return t(
                'user_mailer.note_comment_notification.commented.subject other',
                commenter=comment_user_name,
            )
    elif event == 'closed':
        if is_note_owner:
            return t(
                'user_mailer.note_comment_notification.closed.subject_own',
                commenter=comment_user_name,
            )
        else:
            return t(
                'user_mailer.note_comment_notification.closed.subject other',
                commenter=comment_user_name,
            )
    elif event == 'reopened':
        if is_note_owner:
            return t(
                'user_mailer.note_comment_notification.reopened.subject_own',
                commenter=comment_user_name,
            )
        else:
            return t(
                'user_mailer.note_comment_notification.reopened.subject other',
                commenter=comment_user_name,
            )

    raise NotImplementedError(f'Unsupported activity email note event {event!r}')
