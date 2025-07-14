from contextlib import nullcontext
from typing import Literal

from psycopg import AsyncConnection
from psycopg.sql import SQL

from app.db import db


class TimescaleDBQuery:
    @staticmethod
    async def get_chunks_ranges(
        table: str,
        conn: AsyncConnection | None = None,
        *,
        inclusive: bool = True,
        sort: Literal['asc', 'desc'] = 'desc',
    ) -> list[tuple[int, int]]:
        async with (
            nullcontext(conn) if conn is not None else db() as conn,  # noqa: PLR1704
            await conn.execute(
                SQL("""
                SELECT range_start_integer, range_end_integer {inclusive}
                FROM timescaledb_information.chunks
                WHERE hypertable_name = %s
                ORDER BY range_end_integer {sort}
                """).format(
                    inclusive=SQL('- 1') if inclusive else SQL(''),
                    sort=SQL(sort),
                ),
                (table,),
            ) as r,
        ):
            return await r.fetchall() or [(-2, -1)]
