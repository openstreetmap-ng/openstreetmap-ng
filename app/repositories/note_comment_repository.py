from collections.abc import Sequence

from shapely import Polygon
from sqlalchemy import func, select

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.statement_context import apply_statement_context
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment


class NoteCommentRepository:
    @staticmethod
    async def find_many_by_query(
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
