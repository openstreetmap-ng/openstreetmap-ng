from collections.abc import Sequence

from shapely import Polygon
from sqlalchemy import func, select, union_all

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.statement_context import apply_statement_context
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment


class NoteCommentRepository:
    @staticmethod
    async def legacy_find_many_by_query(
        *,
        geometry: Polygon | None = None,
        limit: int | None,
    ) -> Sequence[NoteComment]:
        """
        Find note comments by query.
        """

        async with db() as session:
            stmt = select(NoteComment).join(Note)
            stmt = apply_statement_context(stmt)
            where_and = [Note.visible_to(auth_user())]

            if geometry is not None:
                where_and.append(func.ST_Intersects(Note.point, geometry.wkt))

            stmt = stmt.where(*where_and).order_by(NoteComment.created_at.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def resolve_comments(
        notes: Sequence[Note],
        *,
        limit_per_note: int | None,
    ) -> None:
        """
        Resolve comments for notes.
        """

        # small optimization
        if not notes:
            return

        async with db() as session:
            stmts = []

            for note in notes:
                stmt_ = (
                    select(NoteComment)
                    .where(
                        NoteComment.note_id == note.id,
                        NoteComment.created_at <= note.updated_at,
                    )
                    .order_by(NoteComment.created_at.desc())
                )

                if limit_per_note is not None:
                    stmt_ = stmt_.limit(limit_per_note)

                stmts.append(stmt_)

            stmt = union_all(*stmts)
            stmt = apply_statement_context(stmt)

            comments: Sequence[NoteComment] = (await session.scalars(stmt)).all()

        note_iter = iter(notes)
        note = next(note_iter)
        # read property once for performance
        note_id = note.id
        note_comments = note.comments = []

        comment_iter = iter(comments)
        comment = next(comment_iter, None)

        while True:
            if comment.note_id == note_id:
                note_comments.append(comment)
                comment = next(comment_iter)
            else:
                note = next(note_iter)
                note_id = note.id
                note_comments = note.comments = []
