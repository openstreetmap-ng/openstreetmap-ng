from collections.abc import Sequence

from shapely import Polygon
from sqlalchemy import func, select

from src.db import DB
from src.lib_cython.auth import auth_user
from src.lib_cython.joinedload_context import get_joinedload
from src.limits import FIND_LIMIT
from src.models.db.note import Note
from src.models.db.note_comment import NoteComment


class NoteCommentRepository:
    @staticmethod
    async def find_many_by_query(
        *,
        geometry: Polygon | None = None,
        limit: int | None = FIND_LIMIT,
    ) -> Sequence[NoteComment]:
        """
        Find note comments by query.
        """

        async with DB() as session:
            stmt = select(NoteComment).options(get_joinedload()).join(Note)
            where_and = [Note.visible_to(auth_user())]

            if geometry:
                where_and.append(func.ST_Intersects(Note.point, geometry.wkt))

            stmt = stmt.where(*where_and).order_by(NoteComment.created_at.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
