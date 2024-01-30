from fastapi import Request
from shapely import Point
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.db import db_autocommit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.lib.joinedload_context import get_joinedload
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.note_event import NoteEvent


class NoteService:
    @staticmethod
    async def create(request: Request, point: Point, text: str) -> Note:
        """
        Create a note.
        """

        if (user := auth_user()) is not None:
            user_id = user.id
            user_ip = None
        else:
            user_id = None
            user_ip = request.client.host

        async with db_autocommit() as session:
            note = Note(
                point=point,
                comments=[
                    NoteComment(
                        user_id=user_id,
                        user_ip=user_ip,
                        event=NoteEvent.opened,
                        body=text,
                    )
                ],
            )

            session.add(note)

        return note

    @staticmethod
    async def comment(note_id: int, text: str, event: NoteEvent) -> Note:
        """
        Comment on a note.
        """

        current_user = auth_user()

        async with db_autocommit() as session:
            stmt = (
                select(Note)
                .options(
                    joinedload(Note.comments),
                    get_joinedload(),
                )
                .where(
                    Note.id == note_id,
                    Note.visible_to(current_user),
                )
                .with_for_update()
            )

            note = await session.scalar(stmt)

            if note is None:
                raise_for().note_not_found(note_id)

            if event == NoteEvent.closed:
                if note.closed_at is not None:
                    raise_for().note_closed(note_id, note.closed_at)

                note.closed_at = func.statement_timestamp()

            elif event == NoteEvent.reopened:
                # unhide
                if note.hidden_at is not None:
                    note.hidden_at = None
                # reopen
                else:
                    if note.closed_at is None:
                        raise_for().note_open(note_id)

                    note.closed_at = None

            elif event == NoteEvent.commented:
                if note.closed_at is not None:
                    raise_for().note_closed(note_id, note.closed_at)

            elif event == NoteEvent.hidden:
                note.hidden_at = func.statement_timestamp()

            else:
                raise RuntimeError(f'Unsupported comment event {event!r}')

            # TODO: will this updated_at ?
            note.comments.append(
                NoteComment(
                    user_id=current_user.id,
                    user_ip=None,
                    event=event,
                    body=text,
                )
            )

        return note
