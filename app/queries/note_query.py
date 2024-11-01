from collections.abc import Collection, Sequence
from datetime import datetime, timedelta
from typing import Literal

from shapely.geometry.base import BaseGeometry
from sqlalchemy import func, null, or_, select, text

from app.db import db
from app.lib.auth_context import auth_user
from app.lib.date_utils import utcnow
from app.lib.options_context import apply_options_context
from app.models.db.note import Note
from app.models.db.note_comment import NoteComment, NoteEvent


class NoteQuery:
    @staticmethod
    async def count_by_user_id(user_id: int) -> int:
        """
        Count notes by user id.
        """
        async with db() as session:
            stmt = select(func.count()).select_from(
                select(text('1'))
                .where(
                    NoteComment.user_id == user_id,
                    NoteComment.event == NoteEvent.opened,
                )
                .subquery()
            )
            return (await session.execute(stmt)).scalar_one()

    @staticmethod
    async def find_many_by_query(
        *,
        note_ids: Collection[int] | None = None,
        phrase: str | None = None,
        user_id: int | None = None,
        event: NoteEvent | None = None,
        max_closed_days: float | None = None,
        geometry: BaseGeometry | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_by: Literal['created_at', 'updated_at'] = 'created_at',
        sort_dir: Literal['asc', 'desc'] = 'desc',
        limit: int | None,
    ) -> Sequence[Note]:
        """
        Find notes by query.
        """
        async with db() as session:
            cte_where_and: list = []

            if phrase is not None:
                cte_where_and.append(func.to_tsvector(NoteComment.body).bool_op('@@')(func.phraseto_tsquery(phrase)))
            if user_id is not None:
                cte_where_and.append(NoteComment.event.in_(tuple(NoteEvent)))
                cte_where_and.append(NoteComment.user_id == user_id)
            if event is not None:
                cte_where_and.append(NoteComment.event == event)

            stmt = select(Note)
            stmt = apply_options_context(stmt)
            where_and = [Note.visible_to(auth_user())]
            sort_key = Note.created_at if sort_by == 'created_at' else Note.updated_at

            if cte_where_and:
                if note_ids:
                    cte_where_and.append(NoteComment.note_id.in_(text(','.join(map(str, note_ids)))))
                cte = (
                    select(NoteComment.note_id)
                    .where(*cte_where_and)
                    .distinct()
                    .cte()  #
                    .prefix_with('MATERIALIZED')
                )
                where_and.append(Note.id.in_(cte.select()))
            elif note_ids:
                where_and.append(Note.id.in_(text(','.join(map(str, note_ids)))))

            if max_closed_days is not None:
                if max_closed_days > 0:
                    where_and.append(
                        or_(
                            Note.closed_at == null(),
                            Note.closed_at >= utcnow() - timedelta(days=max_closed_days),
                        )
                    )
                else:
                    where_and.append(Note.closed_at == null())
            if geometry is not None:
                where_and.append(func.ST_Intersects(Note.point, func.ST_GeomFromText(geometry.wkt, 4326)))
            if date_from is not None:
                where_and.append(sort_key >= date_from)
            if date_to is not None:
                where_and.append(sort_key < date_to)

            stmt = stmt.where(*where_and)
            stmt = stmt.order_by(sort_key.asc() if sort_dir == 'asc' else sort_key.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
