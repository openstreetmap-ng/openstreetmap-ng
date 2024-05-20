from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Literal

from shapely.ops import BaseGeometry
from sqlalchemy import func, null, select, text

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.options_context import apply_options_context
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment


class NoteQuery:
    @staticmethod
    async def find_many_by_query(
        *,
        note_ids: Sequence[int] | None = None,
        phrase: str | None = None,
        user_id: int | None = None,
        max_closed_for: timedelta | None = None,
        geometry: BaseGeometry | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: Literal['created_at', 'updated_at'] = 'created_at',
        sort_ascending: bool = False,
        limit: int | None,
    ) -> Sequence[Note]:
        """
        Find notes by query.
        """
        async with db() as session:
            stmt = select(Note)
            stmt = apply_options_context(stmt)
            where_and = [Note.visible_to(auth_user())]
            sort_key = Note.created_at if sort_by == 'created_at' else Note.updated_at

            if note_ids:
                where_and.append(Note.id.in_(text(','.join(map(str, note_ids)))))
            if phrase is not None:
                where_and.append(func.to_tsvector(NoteComment.body).bool_op('@@')(func.phraseto_tsquery(phrase)))
            if user_id is not None:
                where_and.append(NoteComment.user_id == user_id)
            if max_closed_for is not None:
                if max_closed_for:
                    where_and.append(Note.closed_at >= utcnow() - max_closed_for)
                else:
                    where_and.append(Note.closed_at == null())
            if geometry is not None:
                where_and.append(func.ST_Intersects(Note.point, func.ST_GeomFromText(geometry.wkt, 4326)))
            if date_from is not None:
                where_and.append(sort_key >= date_from)
            if date_to is not None:
                where_and.append(sort_key < date_to)

            stmt = stmt.where(*where_and)

            # logical optimization, skip sort if at most one note will be returned
            if not (note_ids is not None and len(note_ids) == 1):
                stmt = stmt.order_by(sort_key.asc() if sort_ascending else sort_key.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
