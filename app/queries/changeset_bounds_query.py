from shapely import MultiPolygon

from app.db import db
from app.models.db.changeset import Changeset
from app.models.types import ChangesetId


class ChangesetBoundsQuery:
    @staticmethod
    async def resolve_bounds(changesets: list[Changeset]) -> None:
        """Resolve bounds for changesets."""
        if not changesets:
            return

        id_map = {changeset['id']: changeset for changeset in changesets}

        async with (
            db() as conn,
            await conn.execute(
                """
                SELECT changeset_id, ST_Collect(bounds)
                FROM changeset_bounds
                WHERE changeset_id = ANY(%s)
                GROUP BY changeset_id
                """,
                (list(id_map),),
            ) as r,
        ):
            rows: list[tuple[ChangesetId, MultiPolygon]] = await r.fetchall()
            for changeset_id, bounds in rows:
                id_map[changeset_id]['bounds'] = bounds
