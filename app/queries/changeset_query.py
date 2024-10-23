from collections.abc import Collection, Iterable, Sequence
from datetime import datetime
from typing import Literal

from shapely.geometry.base import BaseGeometry
from sqlalchemy import and_, func, null, select, text

from app.db import db
from app.lib.options_context import apply_options_context
from app.models.db.changeset import Changeset
from app.models.db.changeset_bounds import ChangesetBounds


class ChangesetQuery:
    @staticmethod
    async def get_updated_at_by_ids(changeset_ids: Collection[int]) -> dict[int, datetime]:
        """
        Get the updated at timestamp by changeset ids.

        >>> await ChangesetRepository.get_updated_at_by_ids([1, 2])
        {1: datetime(...), 2: datetime(...)}
        """
        if not changeset_ids:
            return {}

        async with db() as session:
            stmt = select(Changeset.id, Changeset.updated_at).where(
                Changeset.id.in_(text(','.join(map(str, changeset_ids))))
            )
            rows: Iterable[tuple[int, datetime]] = (await session.execute(stmt)).all()  # pyright: ignore[reportAssignmentType]
            return dict(rows)

    @staticmethod
    async def count_by_user_id(user_id: int) -> int:
        """
        Count changesets by user id.
        """
        async with db() as session:
            stmt = select(func.count()).select_from(
                select(text('1'))  #
                .where(Changeset.user_id == user_id)
                .subquery()
            )
            return (await session.execute(stmt)).scalar_one()

    @staticmethod
    async def get_user_adjacent_ids(changeset_id: int, *, user_id: int) -> tuple[int | None, int | None]:
        """
        Get the user's previous and next changeset ids.
        """
        async with db() as session:
            stmt_prev = select(func.max(Changeset.id)).where(Changeset.id < changeset_id, Changeset.user_id == user_id)
            stmt_next = select(func.min(Changeset.id)).where(Changeset.id > changeset_id, Changeset.user_id == user_id)
            stmt = stmt_prev.union_all(stmt_next)
            ids: Sequence[int | None] = (await session.scalars(stmt)).all()

        prev_id: int | None = None
        next_id: int | None = None
        for id in ids:
            if id is None:
                continue
            if id < changeset_id:
                prev_id = id
            else:
                next_id = id

        return prev_id, next_id

    @staticmethod
    async def find_by_id(changeset_id: int) -> Changeset | None:
        """
        Find a changeset by id.
        """
        async with db() as session:
            stmt = select(Changeset).where(Changeset.id == changeset_id)
            stmt = apply_options_context(stmt)
            return await session.scalar(stmt)

    @staticmethod
    async def find_many_by_query(
        *,
        changeset_ids: Collection[int] | None = None,
        changeset_id_before: int | None = None,
        user_id: int | None = None,
        created_before: datetime | None = None,
        closed_after: datetime | None = None,
        is_open: bool | None = None,
        geometry: BaseGeometry | None = None,
        legacy_geometry: bool = False,
        sort: Literal['asc', 'desc'] = 'asc',
        limit: int | None,
    ) -> Sequence[Changeset]:
        """
        Find changesets by query.
        """
        async with db() as session:
            stmt = select(Changeset)
            stmt = apply_options_context(stmt)
            where_and: list = []

            if changeset_ids:
                where_and.append(Changeset.id.in_(text(','.join(map(str, changeset_ids)))))
            if changeset_id_before is not None:
                where_and.append(Changeset.id < changeset_id_before)
            if user_id is not None:
                where_and.append(Changeset.user_id == user_id)
            if created_before is not None:
                where_and.append(Changeset.created_at < created_before)
            if closed_after is not None:
                where_and.append(
                    and_(
                        Changeset.closed_at != null(),
                        Changeset.closed_at >= closed_after,
                    )
                )
            if is_open is not None:
                where_and.append(Changeset.closed_at == null() if is_open else Changeset.closed_at != null())
            if geometry is not None:
                geometry_wkt = geometry.wkt
                where_and.append(
                    and_(
                        Changeset.union_bounds != null(),
                        func.ST_Intersects(Changeset.union_bounds, func.ST_GeomFromText(geometry_wkt, 4326)),
                    )
                )
                if not legacy_geometry:
                    where_and.append(
                        Changeset.id.in_(
                            select(ChangesetBounds.changeset_id)
                            .where(func.ST_Intersects(ChangesetBounds.bounds, func.ST_GeomFromText(geometry_wkt, 4326)))
                            .order_by(
                                ChangesetBounds.changeset_id.asc()
                                if sort == 'asc'
                                else ChangesetBounds.changeset_id.desc()
                            )
                            .subquery()
                            .select()
                        )
                    )

            if where_and:
                stmt = stmt.where(*where_and)

            stmt = stmt.order_by(Changeset.id.asc() if sort == 'asc' else Changeset.id.desc())

            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def count_per_day_by_user_id(user_id: int, created_since: datetime) -> dict[datetime, int]:
        """
        Count changesets per day by user id since given date.
        """
        async with db() as session:
            created_date = func.date_trunc('day', Changeset.created_at)
            stmt = (
                select(
                    created_date,
                    func.count(Changeset.id),
                )
                .where(Changeset.user_id == user_id)
                .where(created_date >= created_since)
                .group_by(created_date)
            )
            rows: Iterable[tuple[datetime, int]] = (await session.execute(stmt)).all()  # pyright: ignore[reportAssignmentType]
            return dict(rows)
