from typing import Literal

from psycopg import AsyncConnection

from app.db import db, t_order


class TimescaleDBQuery:
    @staticmethod
    async def get_chunks_ranges(
        table: str,
        conn: AsyncConnection | None = None,
        *,
        inclusive: bool = True,
        sort: Literal['asc', 'desc'] = 'desc',
    ) -> list[tuple[int, int]]:
        inclusive_sql = t'- 1' if inclusive else t''
        sort_sql = t_order(sort)
        async with (
            db(conn) as conn,
            await conn.execute(t"""
                SELECT range_start_integer, range_end_integer {inclusive_sql:q}
                FROM timescaledb_information.chunks
                WHERE hypertable_name = {table}
                ORDER BY range_end_integer {sort_sql:q}
            """) as r,
        ):
            return await r.fetchall() or [(-2, -1)]
