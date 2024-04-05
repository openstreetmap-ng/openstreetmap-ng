import logging
from collections.abc import Sequence

import numpy as np
from shapely import get_coordinates
from shapely.ops import BaseGeometry
from sqlalchemy import func, select

from app.db import db
from app.lib.mercator import mercator
from app.lib.statement_context import apply_statement_context
from app.limits import TRACE_POINT_COORDS_CACHE_EXPIRE
from app.models.db.trace_ import Trace
from app.models.db.trace_point import TracePoint
from app.models.trace_visibility import TraceVisibility
from app.services.cache_service import CacheService

_cache_context = 'TracePointRepository'


# TODO: limit offset for safety
class TracePointRepository:
    @staticmethod
    async def get_many_by_trace(trace_id: int) -> Sequence[TracePoint]:
        """
        Get trace points by trace id.
        """
        async with db() as session:
            stmt = (
                select(TracePoint)
                .where(TracePoint.trace_id == trace_id)
                # this order_by is important for proper formatting
                .order_by(TracePoint.track_idx.asc(), TracePoint.captured_at.asc())
            )
            stmt = apply_statement_context(stmt)
            return (await session.scalars(stmt)).all()

    @staticmethod
    async def find_many_by_geometry(
        geometry: BaseGeometry,
        *,
        limit: int | None,
        legacy_offset: int | None = None,
    ) -> Sequence[TracePoint]:
        """
        Find trace points by geometry.
        """
        geometry_wkt = 'SRID=4326;' + geometry.wkt

        async with db() as session:
            stmt1 = (
                select(TracePoint)
                .where(
                    func.ST_Intersects(TracePoint.point, geometry_wkt),
                    Trace.visibility.in_((TraceVisibility.identifiable, TraceVisibility.trackable)),
                )
                .order_by(
                    TracePoint.trace_id.desc(),
                    TracePoint.track_idx.asc(),
                    TracePoint.captured_at.asc(),
                )
            )
            stmt1 = apply_statement_context(stmt1)
            stmt2 = (
                select(TracePoint)
                .where(
                    func.ST_Intersects(TracePoint.point, geometry_wkt),
                    Trace.visibility.in_((TraceVisibility.public, TraceVisibility.private)),
                )
                .order_by(
                    TracePoint.point.asc(),
                )
            )
            stmt2 = apply_statement_context(stmt2)
            stmt = stmt1.union(stmt2)

            if legacy_offset is not None:
                stmt = stmt.offset(legacy_offset)
            if limit is not None:
                stmt = stmt.limit(limit)

            return (await session.scalars(stmt)).all()

    @staticmethod
    async def get_image_coords_by_id(trace_id: int, n: int = 200) -> list[int]:
        """
        Get coords list for rendering an icon.

        >>> get_image_coords_by_id(...)
        [x1, y1, x2, y2, ...]
        """
        async with db() as session:
            stmt = select(Trace.size).where(Trace.id == trace_id).with_for_update()
            size = await session.scalar(stmt)
            if size is None or size < 2:
                return ()

            async def factory() -> bytes:
                logging.debug('Image coords cache miss for trace %d', trace_id)
                stmt = (
                    select(TracePoint.point)  #
                    .where(TracePoint.trace_id == trace_id)
                    .order_by(TracePoint.track_idx.asc(), TracePoint.captured_at.asc())
                )

                if size > n:
                    indices = np.round(np.linspace(0, size, n)).astype(int)
                    stmt = (
                        select(TracePoint.point)  #
                        .select_from(stmt.subquery())
                        .where(func.row_number().in_(indices))
                    )

                points = (await session.scalars(stmt)).all()
                coords = mercator(get_coordinates(points), 100, 100).astype(np.byte).flatten()
                return bytes(coords)  # this is possible because coords fit in 1 byte

            key = f'{trace_id}:{n}'
            cache_entry = await CacheService.get_one_by_key(
                key=key.encode(),
                context=_cache_context,
                factory=factory,
                ttl=TRACE_POINT_COORDS_CACHE_EXPIRE,
            )

            return list(cache_entry.value)
