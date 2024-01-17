from collections.abc import Sequence
from datetime import datetime

from shapely import Polygon
from sqlalchemy import func, null, select

from src.db import DB
from src.lib_cython.joinedload_context import get_joinedload
from src.limits import FIND_LIMIT
from src.models.db.changeset import Changeset


class ChangesetRepository:
    @staticmethod
    async def find_many_by_query(
        *,
        changeset_ids: Sequence[int] | None = None,
        user_id: int | None = None,
        created_before: datetime | None = None,
        closed_after: datetime | None = None,
        is_open: bool | None = None,
        geometry: Polygon | None = None,
        limit: int | None = FIND_LIMIT,
    ) -> Sequence[Changeset]:
        """
        Find changesets by query.
        """

        async with DB() as session:
            stmt = select(Changeset).options(get_joinedload())
            where_and = []

            if changeset_ids:
                where_and.append(Changeset.id.in_(changeset_ids))
            if user_id:
                where_and.append(Changeset.user_id == user_id)
            if created_before:
                where_and.append(Changeset.created_at < created_before)
            if closed_after:
                where_and.append(Changeset.closed_at >= closed_after)
            if is_open is not None:
                if is_open:
                    where_and.append(Changeset.closed_at == null())
                else:
                    where_and.append(Changeset.closed_at != null())
            if geometry:
                where_and.append(func.ST_Intersects(Changeset.boundary, geometry.wkt))

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

        async with DB() as session:
            stmt = select(func.count()).select_from(
                select(Changeset).where(
                    Changeset.user_id == user_id,
                )
            )

            return await session.scalar(stmt)
