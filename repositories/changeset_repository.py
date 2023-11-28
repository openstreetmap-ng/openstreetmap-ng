from collections.abc import Sequence
from datetime import datetime

from shapely import Polygon
from sqlalchemy import func, null, select
from sqlalchemy.orm import joinedload

from db import DB
from limits import FIND_LIMIT
from models.db.changeset import Changeset


class ChangesetRepository:
    @staticmethod
    async def find_one_by_id(
        changeset_id: int,
        *,
        include_comments: bool = False,
        include_elements: bool = False,
    ) -> Changeset | None:
        """
        Find a changeset by id.
        """

        async with DB() as session:
            options = []

            if include_comments:
                options.append(joinedload(Changeset.changeset_comments))
            if include_elements:
                options.append(joinedload(Changeset.elements))

            return await session.get(Changeset, changeset_id, options=options)

    @staticmethod
    async def find_many_by_query(
        *,
        changeset_ids: Sequence[int] | None = None,
        user_id: int | None = None,
        created_before: datetime | None = None,
        closed_after: datetime | None = None,
        is_open: bool | None = None,
        geometry: Polygon | None = None,
        include_comments: bool = False,
        limit: int | None = FIND_LIMIT,
    ):
        async with DB() as session:
            options = []

            if include_comments:
                options.append(joinedload(Changeset.changeset_comments))

            stmt = select(Changeset).options(options)

            if changeset_ids:
                stmt = stmt.where(Changeset.id.in_(changeset_ids))
            if user_id:
                stmt = stmt.where(Changeset.user_id == user_id)
            if created_before:
                stmt = stmt.where(Changeset.created_at < created_before)
            if closed_after:
                stmt = stmt.where(Changeset.closed_at >= closed_after)
            if is_open is True:
                stmt = stmt.where(Changeset.closed_at == null())
            if is_open is False:
                stmt = stmt.where(Changeset.closed_at != null())
            if geometry:
                stmt = stmt.where(func.ST_Intersects(Changeset.boundary, geometry.wkt))
            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()
