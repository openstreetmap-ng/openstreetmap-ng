from asyncio import TaskGroup
from datetime import datetime
from typing import Any

import cython
from shapely import Point, get_coordinates

from app.db import db, db_fetchone, db_insert, db_update
from app.exceptions.context import raise_for
from app.lib.audit import audit
from app.lib.auth.context import auth_scopes, auth_user
from app.lib.http.client import HTTPError
from app.lib.text.translation import t, translation_context
from app.middlewares.request_context_middleware import get_request_ip
from app.models.db.note import Note
from app.models.db.note_comment import (
    NoteComment,
    note_comments_resolve_rich_text,
)
from app.models.db.user import user_is_moderator
from app.models.proto.note_types import GetCommentsResponse_Comment_Event
from app.models.types import DisplayName, NoteCommentId, NoteId
from app.queries.nominatim_query import NominatimQuery
from app.queries.note_query import NoteCommentQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.email_service import EmailService
from app.services.user_subscription_service import UserSubscriptionService
from app.validators.geometry import validate_geometry

_NOTE_CREATE_HASHTAG = '#osm-ng'


class NoteService:
    @staticmethod
    async def create(lon: float, lat: float, text: str) -> NoteId:
        """Create a note and return its id."""
        point = validate_geometry(Point(lon, lat))
        text = _with_note_create_hashtag(text)

        user = auth_user()
        if user is not None:
            # Prevent OAuth to create user-authorized note
            scopes = auth_scopes()
            if 'web_user' not in scopes and 'write_notes' not in scopes:
                raise_for.insufficient_scopes(['write_notes'])
            user_id = user['id']
            user_ip = None
        else:
            user_id = None
            user_ip = get_request_ip()

        async with db(True) as conn:
            note_id: NoteId
            note_created_at: datetime
            note_id, note_created_at = await db_insert(
                'note',
                {'point': t'ST_QuantizeCoordinates({point}, 7)'},
                returning='id, created_at',
                conn=conn,
            )

            await db_insert(
                'note_comment',
                {
                    'user_id': user_id,
                    'user_ip': user_ip,
                    'note_id': note_id,
                    'event': 'opened',
                    'body': text,
                    'created_at': note_created_at,
                },
                conn=conn,
            )
            await audit('create_note', conn, extra={'id': note_id})

        if user_id is not None:
            await UserSubscriptionService.subscribe('note', note_id)

        return note_id

    @staticmethod
    async def comment(
        note_id: NoteId, text: str, event: GetCommentsResponse_Comment_Event
    ):
        """Comment on a note."""
        user = auth_user(required=True)
        user_id = user['id']
        send_activity_email: cython.bint = False

        # Only show hidden notes to moderators
        hidden_filter = t'' if user_is_moderator(user) else t'AND hidden_at IS NULL'

        async with db(True) as conn:
            note = await db_fetchone(
                Note,
                t"""
                    SELECT * FROM note
                    WHERE id = {note_id}
                    {hidden_filter:q}
                    FOR UPDATE
                """,
                conn=conn,
            )
            if note is None:
                raise_for.note_not_found(note_id)

            updates: dict[str, Any] = {}

            if event == 'closed':
                if note['closed_at'] is not None:
                    raise_for.note_closed(note_id, note['closed_at'])
                updates['closed_at'] = t'statement_timestamp()'
                send_activity_email = True

            elif event == 'reopened':
                # Unhide
                if note['hidden_at'] is not None:
                    updates['hidden_at'] = None
                # Reopen
                elif note['closed_at'] is None:
                    raise_for.note_open(note_id)
                else:
                    updates['closed_at'] = None
                    send_activity_email = True

            elif event == 'commented':
                if note['closed_at'] is not None:
                    raise_for.note_closed(note_id, note['closed_at'])
                send_activity_email = True

            elif event == 'hidden':
                if not user_is_moderator(user):
                    raise_for.insufficient_scopes(['role_moderator'])
                updates['hidden_at'] = t'statement_timestamp()'

            else:
                raise NotImplementedError(f'Unsupported note event {event!r}')

            comment_id: NoteCommentId
            created_at: datetime
            comment_id, created_at = await db_insert(
                'note_comment',
                {
                    'user_id': user_id,
                    'user_ip': None,
                    'note_id': note_id,
                    'event': event,
                    'body': text,
                },
                returning='id, created_at',
                conn=conn,
            )

            # Update the note's updated_at to match the comment's created_at
            updates['updated_at'] = created_at
            await db_update('note', updates, where={'id': note_id}, conn=conn)
            if text:
                await audit(
                    'create_note_comment',
                    conn,
                    extra={'id': comment_id, 'note': note_id},
                )
            if event != 'commented':
                await audit(
                    'update_note_status',
                    conn,
                    extra={'id': note_id, 'event': event},
                )

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


async def _send_activity_email(note: Note, comment: NoteComment):
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
        header_t = tg.create_task(NoteCommentQuery.find_header(note['id']))

        users = await UserSubscriptionQuery.get_subscribed_users(
            'note', comment['note_id']
        )
        if not users:
            return

    place = place_t.result()
    header = header_t.result()
    assert header is not None, 'Note must have at least one comment'
    header_user_id: cython.size_t = header['user_id'] or 0

    assert comment['user_id'] is not None, (
        'Anonymous note comments are no longer supported'
    )
    comment_user = comment['user']  # pyright: ignore [reportTypedDictNotRequiredAccess]
    comment_user_id: cython.size_t = comment_user['id']
    comment_user_name = comment_user['display_name']
    comment_event = comment['event']
    ref = f'note-{note["id"]}'

    async with TaskGroup() as tg:
        for subscribed_user in users:
            subscribed_user_id: cython.size_t = subscribed_user['id']
            if subscribed_user_id == comment_user_id:
                continue

            with translation_context(subscribed_user['language']):
                is_note_owner: cython.bint = subscribed_user_id == header_user_id
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


def _with_note_create_hashtag(text: str):
    if _NOTE_CREATE_HASHTAG.lower() in text.lower():
        return text
    return f'{text}\n\n{_NOTE_CREATE_HASHTAG}'


@cython.cfunc
def _get_activity_email_subject(
    comment_user_name: DisplayName,
    event: GetCommentsResponse_Comment_Event,
    is_note_owner: cython.bint,
):
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
