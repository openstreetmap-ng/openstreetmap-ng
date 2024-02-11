from collections.abc import Sequence
from datetime import datetime, timedelta

from shapely import Polygon
from sqlalchemy import func, null, select

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.joinedload_context import get_joinedload
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment


class NoteRepository:
    @staticmethod
    async def find_many_by_query(
        *,
        note_ids: Sequence[int] | None = None,
        text: str | None = None,
        user_id: int | None = None,
        max_closed_for: timedelta | None = None,
        geometry: Polygon | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by_created: bool = True,
        sort_asc: bool = False,
        limit: int | None,
    ) -> Sequence[Note]:
        """
        Find notes by query.
        """

        async with db() as session:
            stmt = select(Note).options(get_joinedload()).join(NoteComment)
            where_and = [Note.visible_to(auth_user())]
            sort_by_key = Note.created_at if sort_by_created else Note.updated_at

            if note_ids:
                where_and.append(Note.id.in_(note_ids))
            if text is not None:
                where_and.append(func.to_tsvector(NoteComment.body).bool_op('@@')(func.phraseto_tsquery(text)))
            if user_id is not None:
                where_and.append(NoteComment.user_id == user_id)
            if max_closed_for is not None:
                if max_closed_for:
                    where_and.append(Note.closed_at >= utcnow() - max_closed_for)
                else:
                    where_and.append(Note.closed_at == null())
            if geometry is not None:
                where_and.append(func.ST_Intersects(Note.point, geometry.wkt))
            if date_from is not None:
                where_and.append(sort_by_key >= date_from)
            if date_to is not None:
                where_and.append(sort_by_key < date_to)

            stmt = stmt.where(*where_and)

            # logical optimization, skip sort if at most one note will be returned
            if not (note_ids is not None and len(note_ids) == 1):
                stmt = stmt.order_by(sort_by_key.asc() if sort_asc else sort_by_key.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
