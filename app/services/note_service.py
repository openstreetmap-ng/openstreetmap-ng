import logging
from asyncio import TaskGroup

import cython
import numpy as np
from httpx import HTTPError
from shapely import Point, lib
from shapely.coordinates import get_coordinates
from sqlalchemy import delete, exists, func, select

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.translation import t, translation_context
from app.limits import GEO_COORDINATE_PRECISION
from app.middlewares.request_context_middleware import get_request_ip
from app.models.db.mail import MailSource
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment, NoteEvent
from app.models.db.user import User
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.scope import Scope
from app.models.types import DisplayNameType
from app.queries.nominatim_query import NominatimQuery
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.email_service import EmailService
from app.services.user_subscription_service import UserSubscriptionService
from app.validators.geometry import validate_geometry


class NoteService:
    @staticmethod
    async def create(lon: float, lat: float, text: str) -> int:
        """
        Create a note and return its id.
        """
        coordinate_precision = GEO_COORDINATE_PRECISION
        point: Point = lib.points(np.array((lon, lat), np.float64).round(coordinate_precision))
        point = validate_geometry(point)
        user = auth_user()
        if user is not None:
            user_id = user.id
            user_ip = None
        else:
            user_id = None
            user_ip = get_request_ip()

        async with db_commit() as session:
            note = Note(point=point)
            session.add(note)
            await session.flush()

            note_comment = NoteComment(
                user_id=user_id,
                user_ip=user_ip,
                note_id=note.id,
                event=NoteEvent.opened,
                body=text,
            )
            session.add(note_comment)
            await session.flush()

            note.updated_at = note_comment.created_at

        note_id = note.id
        if user_id is not None:
            logging.debug('Created note %d by user %d', note_id, user_id)
            await UserSubscriptionService.subscribe(UserSubscriptionTarget.note, note_id)
        else:
            logging.debug('Created note %d by anonymous user', note_id)
        return note_id

    @staticmethod
    async def comment(note_id: int, text: str, event: NoteEvent) -> None:
        """
        Comment on a note.
        """
        user = auth_user(required=True)
        send_activity_email: cython.char = False
        async with db_commit() as session:
            stmt = select(Note).where(Note.id == note_id, Note.visible_to(user)).with_for_update()
            note = await session.scalar(stmt)
            if note is None:
                raise_for.note_not_found(note_id)

            if event == NoteEvent.closed:
                if note.closed_at is not None:
                    raise_for.note_closed(note_id, note.closed_at)
                note.closed_at = func.statement_timestamp()
                send_activity_email = True

            elif event == NoteEvent.reopened:
                # unhide
                if note.hidden_at is not None:
                    note.hidden_at = None
                # reopen
                else:
                    if note.closed_at is None:
                        raise_for.note_open(note_id)
                    note.closed_at = None
                    send_activity_email = True

            elif event == NoteEvent.commented:
                if note.closed_at is not None:
                    raise_for.note_closed(note_id, note.closed_at)
                send_activity_email = True

            elif event == NoteEvent.hidden:
                if not user.is_moderator:
                    raise_for.insufficient_scopes((Scope.role_moderator,))
                note.hidden_at = func.statement_timestamp()

            else:
                raise NotImplementedError(f'Unsupported note event {event!r}')

            note_comment = NoteComment(
                user_id=user.id,
                user_ip=None,
                note_id=note_id,
                event=event,
                body=text,
            )
            session.add(note_comment)
            await session.flush((note_comment,))

            note.updated_at = note_comment.created_at

        logging.debug('Created note comment on note %d by user %d', note_id, user.id)
        note_comment.user = user
        async with TaskGroup() as tg:
            if send_activity_email:
                tg.create_task(_send_activity_email(note, note_comment))
            tg.create_task(UserSubscriptionService.subscribe(UserSubscriptionTarget.note, note_id))

    @staticmethod
    async def delete_notes_without_comments() -> None:
        """
        Find all notes without comments and delete them.
        """
        logging.info('Deleting notes without comments')
        async with db_commit() as session:
            stmt = delete(Note).where(~exists().where(Note.id == NoteComment.note_id))
            result = await session.execute(stmt)
            if result.rowcount:
                logging.info('Deleted %d notes without comments', result.rowcount)
            else:
                logging.warning('Not found any notes without comments')


async def _send_activity_email(note: Note, comment: NoteComment) -> None:
    async def place_task() -> str:
        try:
            # reverse geocode the note point
            result = await NominatimQuery.reverse(note.point)
            if result is not None:
                return result.display_name
        except HTTPError:
            pass
        x, y = get_coordinates(note.point)[0].tolist()
        return f'{y:.5f}, {x:.5f}'

    async with TaskGroup() as tg:
        tg.create_task(comment.resolve_rich_text())
        place_t = tg.create_task(place_task())
        first_comment_t = tg.create_task(
            NoteCommentQuery.resolve_comments(
                (note,),
                per_note_sort='asc',
                per_note_limit=1,
                resolve_rich_text=False,
            )
        )
        users = await UserSubscriptionQuery.get_subscribed_users(UserSubscriptionTarget.note, comment.note_id)
        if not users:
            return

    place = place_t.result()
    first_comment_user_id: cython.longlong = first_comment_t.result()[0].id
    comment_user: User = comment.user  # type: ignore
    comment_user_id: cython.longlong = comment_user.id
    comment_user_name = comment_user.display_name
    comment_event = comment.event
    async with TaskGroup() as tg:
        for subscribed_user in users:
            subscribed_user_id: cython.longlong = subscribed_user.id
            if subscribed_user_id == comment_user_id:
                continue
            is_note_owner: cython.char = subscribed_user_id == first_comment_user_id
            with translation_context(subscribed_user.language):
                subject = _get_activity_email_subject(comment_user_name, comment_event, is_note_owner)
            tg.create_task(
                EmailService.schedule(
                    source=MailSource.system,
                    from_user=None,
                    to_user=subscribed_user,
                    subject=subject,
                    template_name='email/note_activity.jinja2',
                    template_data={'comment': comment, 'is_note_owner': is_note_owner, 'place': place},
                )
            )


@cython.cfunc
def _get_activity_email_subject(
    comment_user_name: DisplayNameType,
    event: NoteEvent,
    is_note_owner: cython.char,
) -> str:
    if event == NoteEvent.commented:
        if is_note_owner:
            return t('user_mailer.note_comment_notification.commented.subject_own', commenter=comment_user_name)
        else:
            return t('user_mailer.note_comment_notification.commented.subject other', commenter=comment_user_name)
    elif event == NoteEvent.closed:
        if is_note_owner:
            return t('user_mailer.note_comment_notification.closed.subject_own', commenter=comment_user_name)
        else:
            return t('user_mailer.note_comment_notification.closed.subject other', commenter=comment_user_name)
    elif event == NoteEvent.reopened:
        if is_note_owner:
            return t('user_mailer.note_comment_notification.reopened.subject_own', commenter=comment_user_name)
        else:
            return t('user_mailer.note_comment_notification.reopened.subject other', commenter=comment_user_name)
    raise NotImplementedError(f'Unsupported note event {event!r}')
