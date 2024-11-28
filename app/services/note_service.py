import logging

import numpy as np
from shapely import Point, lib
from sqlalchemy import delete, exists, func, select

from app.db import db_commit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.limits import GEO_COORDINATE_PRECISION
from app.middlewares.request_context_middleware import get_request_ip
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment, NoteEvent
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.scope import Scope
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
        async with db_commit() as session:
            stmt = select(Note).where(Note.id == note_id, Note.visible_to(user)).with_for_update()
            note = await session.scalar(stmt)
            if note is None:
                raise_for.note_not_found(note_id)

            if event == NoteEvent.closed:
                if note.closed_at is not None:
                    raise_for.note_closed(note_id, note.closed_at)
                note.closed_at = func.statement_timestamp()

            elif event == NoteEvent.reopened:
                # unhide
                if note.hidden_at is not None:
                    note.hidden_at = None
                # reopen
                else:
                    if note.closed_at is None:
                        raise_for.note_open(note_id)
                    note.closed_at = None

            elif event == NoteEvent.commented:
                if note.closed_at is not None:
                    raise_for.note_closed(note_id, note.closed_at)

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
        await UserSubscriptionService.subscribe(UserSubscriptionTarget.note, note_id)

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
