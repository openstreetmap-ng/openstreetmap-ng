from collections.abc import Sequence
from datetime import datetime

from shapely.ops import BaseGeometry
from sqlalchemy import func, null, select, text

from app.db import db
from app.lib.options_context import apply_options_context
from app.models.db.changeset import Changeset


class ChangesetQuery:
    @staticmethod
    async def get_updated_at_by_ids(changeset_ids: Sequence[int]) -> dict[int, datetime]:
        """
        Get the updated at timestamp by changeset ids.

        >>> await ChangesetRepository.get_updated_at_by_ids([1, 2])
        {1: datetime(...), 2: datetime(...)}
        """
        async with db() as session:
            stmt = select(Changeset.id, Changeset.updated_at).where(
                Changeset.id.in_(text(','.join(map(str, changeset_ids))))
            )
            rows = (await session.execute(stmt)).all()
            return dict(rows)

    @staticmethod
    async def get_adjacent_ids(changeset_id: int, *, user_id: int) -> tuple[int | None, int | None]:
        """
        Get the user's previous and next changeset ids.
        """
        async with db() as session:
            stmt_prev = select(func.max(Changeset.id)).where(Changeset.id < changeset_id, Changeset.user_id == user_id)
            stmt_next = select(func.min(Changeset.id)).where(Changeset.id > changeset_id, Changeset.user_id == user_id)
            stmt = stmt_prev.union_all(stmt_next)
            ids: Sequence[int] = (await session.scalars(stmt)).all()

        prev_id: int | None = None
        next_id: int | None = None

        for id in ids:
            if id < changeset_id:
                prev_id = id
            else:
                next_id = id

        return prev_id, next_id

    @staticmethod
    async def find_many_by_query(
        *,
        changeset_ids: Sequence[int] | None = None,
        user_id: int | None = None,
        created_before: datetime | None = None,
        closed_after: datetime | None = None,
        is_open: bool | None = None,
        geometry: BaseGeometry | None = None,
        limit: int | None,
    ) -> Sequence[Changeset]:
        """
        Find changesets by query.
        """
        async with db() as session:
            stmt = select(Changeset)
            stmt = apply_options_context(stmt)
            where_and = []

            if changeset_ids:
                where_and.append(Changeset.id.in_(text(','.join(map(str, changeset_ids)))))
            if user_id is not None:
                where_and.append(Changeset.user_id == user_id)
            if created_before is not None:
                where_and.append(Changeset.created_at < created_before)
            if closed_after is not None:
                where_and.append(Changeset.closed_at >= closed_after)
            if is_open is not None:
                if is_open:
                    where_and.append(Changeset.closed_at == null())
                else:
                    where_and.append(Changeset.closed_at != null())
            if geometry is not None:
                where_and.append(func.ST_Intersects(Changeset.bounds, func.ST_GeomFromText(geometry.wkt, 4326)))

            if where_and:
                stmt = stmt.where(*where_and)
            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def count_by_user_id(user_id: int) -> int:
        """
        Count changesets by user id.
        """
        async with db() as session:
            stmt = select(func.count()).select_from(select(text('1')).where(Changeset.user_id == user_id))
            return await session.scalar(stmt)
