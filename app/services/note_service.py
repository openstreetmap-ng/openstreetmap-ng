from shapely import Point
from sqlalchemy import func, select

from app.db import db_autocommit
from app.lib.auth_context import auth_user
from app.lib.exceptions_context import raise_for
from app.middlewares.request_context_middleware import get_request_ip
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment
from app.models.note_event import NoteEvent


class NoteService:
    @staticmethod
    async def create(point: Point, text: str) -> int:
        """
        Create a note and return its id.
        """

        if (user := auth_user()) is not None:
            user_id = user.id
            user_ip = None
        else:
            user_id = None
            user_ip = get_request_ip()

        async with db_autocommit() as session:
            note = Note(point=point)
            session.add(note)
            await session.flush()

            session.add(
                NoteComment(
                    user_id=user_id,
                    user_ip=user_ip,
                    note_id=note.id,
                    event=NoteEvent.opened,
                    body=text,
                )
            )

        return note.id

    @staticmethod
    async def comment(note_id: int, text: str, event: NoteEvent) -> None:
        """
        Comment on a note.
        """

        user = auth_user()

        async with db_autocommit() as session:
            stmt = (
                select(Note)
                .where(
                    Note.id == note_id,
                    Note.visible_to(user),
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
                raise NotImplementedError(f'Unsupported note event {event!r}')

            # force update note object
            note.updated_at = func.statement_timestamp()

            session.add(
                NoteComment(
                    user_id=user.id,
                    user_ip=None,
                    note_id=note_id,
                    event=event,
                    body=text,
                )
            )
