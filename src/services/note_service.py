from fastapi import Request
from shapely import Point
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from src.db import DB
from src.lib.exceptions import raise_for
from src.lib_cython.auth import auth_user
from src.lib_cython.joinedload_context import get_joinedload
from src.models.db.note import Note
from src.models.db.note_comment import NoteComment
from src.models.note_event import NoteEvent


class NoteService:
    @staticmethod
    async def create(request: Request, point: Point, text: str) -> Note:
        """
        Create a note.
        """

        if user := auth_user():
            user_id = user.id
            user_ip = None
        else:
            user_id = None
            user_ip = request.client.host

        async with DB() as session, session.begin():
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

        async with DB() as session, session.begin():
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

            if not note:
                raise_for().note_not_found(note_id)

            if event == NoteEvent.closed:
                if note.closed_at:
                    raise_for().note_closed(note_id, note.closed_at)

                note.closed_at = func.now()

            elif event == NoteEvent.reopened:
                # unhide
                if note.hidden_at:
                    note.hidden_at = None
                # reopen
                else:
                    if not note.closed_at:
                        raise_for().note_open(note_id)

                    note.closed_at = None

            elif event == NoteEvent.commented:
                if note.closed_at:
                    raise_for().note_closed(note_id, note.closed_at)

            elif event == NoteEvent.hidden:
                note.hidden_at = func.now()

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
