from collections.abc import Sequence
from datetime import datetime

from shapely import Polygon
from sqlalchemy import func, null, select

from app.db import db
from app.lib.statement_context import apply_statement_context
from app.models.db.changeset import Changeset


class ChangesetRepository:
    @staticmethod
    async def get_updated_at_by_ids(changeset_ids: Sequence[int]) -> dict[int, datetime]:
        """
        Get the updated at timestamp by changeset ids.

        >>> await ChangesetRepository.get_updated_at_by_ids([1, 2])
        {1: datetime(...), 2: datetime(...)}
        """

        async with db() as session:
            stmt = select(Changeset.id, Changeset.updated_at).where(Changeset.id.in_(changeset_ids))
            rows = (await session.execute(stmt)).all()
            return dict(rows)

    @staticmethod
    async def find_many_by_query(
        *,
        changeset_ids: Sequence[int] | None = None,
        user_id: int | None = None,
        created_before: datetime | None = None,
        closed_after: datetime | None = None,
        is_open: bool | None = None,
        geometry: Polygon | None = None,
        limit: int | None,
    ) -> Sequence[Changeset]:
        """
        Find changesets by query.
        """

        async with db() as session:
            stmt = select(Changeset)
            stmt = apply_statement_context(stmt)

            where_and = []

            if changeset_ids:
                where_and.append(Changeset.id.in_(changeset_ids))
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
                where_and.append(func.ST_Intersects(Changeset.bounds, geometry.wkt))

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
            stmt = select(func.count()).select_from(
                select(Changeset).where(Changeset.user_id == user_id)  #
            )

            return await session.scalar(stmt)
