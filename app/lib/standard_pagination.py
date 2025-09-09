from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, LiteralString

import cython
from psycopg import AsyncConnection
from psycopg.sql import SQL, Composable

from app.models.proto.shared_pb2 import Cursor, PageCursors

if cython.compiled:
    from cython.cimports.libc.math import ceil
else:
    from math import ceil


def standard_pagination_range(
    page: cython.int,
    *,
    page_size: cython.ulonglong,
    num_items: cython.ulonglong,
    reverse: bool = True,
) -> tuple[int, int]:
    """
    Get the range of items for the given page.

    Two pagination modes:
    - reverse=True (default): Optimized for accessing the end of result sets.
      Last page has offset 0, page 1 has the highest offset.
      Efficient when users typically view the last page (newest comments, recent activity).

    - reverse=False: Optimized for accessing the start of result sets.
      Page 1 has offset 0, last page has the highest offset.
      Efficient when users typically start from page 1 (alphabetical lists, search results).

    Returns a tuple of (limit, offset).
    """
    num_pages: cython.int = int(ceil(num_items / page_size))  # noqa: RUF046
    if not (1 <= page <= num_pages):
        return 0, 0

    offset: cython.ulonglong = (
        (num_pages - page) * page_size if reverse else (page - 1) * page_size
    )
    limit: cython.ulonglong = min(page_size, num_items - offset)
    return limit, offset


# ==========================
# Cursor-based pagination
# ==========================


@dataclass(frozen=True)
class _Bounds:
    start: str | None
    end: str | None


async def compute_page_cursors_bin(
    conn: AsyncConnection,
    base_sql: Composable,
    params: list,
    *,
    primary_col: LiteralString,
    page_size: int,
    order: Literal['asc', 'desc'] = 'desc',
    time_ordered: bool = True,
) -> str:
    """
    Compute page anchors as a single base64-encoded PageCursors blob.

    base_sql should select at least the primary column.
    The resulting anchors contain one end-of-page cursor per page, in order.
    """
    order_sql = SQL('ASC') if order == 'asc' else SQL('DESC')
    query = SQL(
        """
        WITH ranked AS (
            SELECT {primary} AS primary_value,
                   ROW_NUMBER() OVER (ORDER BY {primary} {order}) AS rn,
                   COUNT(*) OVER () AS total
            FROM ({base}) base
        )
        SELECT primary_value
        FROM ranked
        WHERE (rn % %s = 0) OR (rn = total)
        ORDER BY rn
        """
    ).format(primary=SQL(primary_col), order=order_sql, base=base_sql)

    anchors: list[Cursor] = []
    async with conn.cursor() as cur:
        await cur.execute(query, [*params, page_size])
        rows = await cur.fetchall()
        for (primary_value,) in rows:
            if time_ordered:
                # Expect datetime; convert to microseconds since epoch
                if isinstance(primary_value, datetime):
                    dt = primary_value.astimezone(UTC)
                    micros = int(dt.timestamp() * 1_000_000)
                else:  # fallback: assume epoch seconds
                    micros = int(primary_value) * 1_000_000
                anchors.append(Cursor(id=micros))
            else:
                anchors.append(Cursor(id=int(primary_value)))

    data = PageCursors(anchors=anchors).SerializeToString()
    return base64.b64encode(data).decode('ascii')


def where_between_sql(
    *,
    primary_col: LiteralString,
    order: Literal['asc', 'desc'] = 'desc',
    time_ordered: bool = True,
    start: str | None,
    end: str | None,
) -> tuple[Composable, list]:
    """
    Build a stable window on the primary column using start/end cursors.

    DESC: primary <= start AND (primary > end if end)
    ASC:  primary >= start AND (primary < end if end)
    """
    if not start:
        raise ValueError('start cursor is required for window pagination')

    start_val = _decode_cursor_primary(start, time_ordered)
    end_val = _decode_cursor_primary(end, time_ordered) if end else None

    ops = ('<=', '>') if order == 'desc' else ('>=', '<')

    params: list = [start_val]
    if end_val is not None:
        where_sql = SQL('({col} {op_start} %s) AND ({col} {op_end} %s)').format(
            col=SQL(primary_col), op_start=SQL(ops[0]), op_end=SQL(ops[1])
        )
        params.append(end_val)
    else:
        where_sql = SQL('{col} {op_start} %s').format(
            col=SQL(primary_col), op_start=SQL(ops[0])
        )
    return where_sql, params


def _decode_cursor_primary(token: str, time_ordered: bool) -> int | datetime:
    data = base64.b64decode(token)
    cur = Cursor()
    cur.ParseFromString(data)
    if time_ordered:
        # Convert microseconds to aware UTC datetime
        return datetime.fromtimestamp(cur.id / 1_000_000, tz=UTC)
    return int(cur.id)
