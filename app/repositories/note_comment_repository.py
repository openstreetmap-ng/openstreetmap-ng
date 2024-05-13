from collections.abc import Sequence

from shapely.ops import BaseGeometry
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
        geometry: BaseGeometry | None = None,
        limit: int | None,
    ) -> Sequence[NoteComment]:
        """
        Find note comments by query.
        """
        async with db() as session:
            stmt = select(NoteComment)
            stmt = apply_statement_context(stmt)
            where_and = [Note.visible_to(auth_user())]

            if geometry is not None:
                where_and.append(func.ST_Intersects(Note.point, func.ST_GeomFromText(geometry.wkt, 4326)))

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
                    select(NoteComment.id)
                    .where(
                        NoteComment.note_id == note.id,
                        NoteComment.created_at <= note.updated_at,
                    )
                    .order_by(NoteComment.created_at.desc())
                )
                stmt_ = apply_statement_context(stmt_)

                if limit_per_note is not None:
                    stmt_ = stmt_.limit(limit_per_note)

                stmts.append(stmt_)

            stmt = (
                select(NoteComment)
                .where(NoteComment.id.in_(union_all(*stmts).subquery().select()))
                .order_by(NoteComment.created_at.desc())
            )
            stmt = apply_statement_context(stmt)

            comments: Sequence[NoteComment] = (await session.scalars(stmt)).all()

        # TODO: delete notes without comments

        id_comments_map: dict[int, list[NoteComment]] = {}
        for note in notes:
            id_comments_map[note.id] = note.comments = []
        for comment in comments:
            id_comments_map[comment.note_id].append(comment)
