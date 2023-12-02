from collections.abc import Sequence

from shapely import Polygon
from sqlalchemy import func, select

from db import DB
from lib.auth import auth_user
from limits import FIND_LIMIT
from models.db.note import Note
from models.db.note_comment import NoteComment


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
            stmt = select(NoteComment).join(Note)
            where_and = [Note.visible_to(auth_user())]  # TODO: or NoteComment.note ?

            if geometry:
                where_and.append(func.ST_Intersects(Note.point, geometry.wkt))

            stmt = stmt.where(*where_and).order_by(NoteComment.created_at.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
