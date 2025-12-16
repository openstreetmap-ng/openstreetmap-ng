from __future__ import annotations

from base64 import urlsafe_b64encode
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, LiteralString, NamedTuple, TypeVar

import cython
from fastapi import Body
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.sql import SQL, Composable, Identifier
from starlette.responses import Response

from app.config import (
    STANDARD_PAGINATION_COUNT_MAX_PAGES,
    STANDARD_PAGINATION_DISTANCE,
    STANDARD_PAGINATION_MAX_FULL_PAGES,
)
from app.db import db
from app.lib.render_response import render_response
from app.models.proto.shared_pb2 import StandardPaginationState


class _SpCursorCodec(NamedTuple):
    encode: Callable[[Any], int | str]
    decode: Callable[[int | str], Any]
    empty: int | str
    storage: Literal['u64', 'text']


class _StandardPaginationQueryPlan(NamedTuple):
    order_dir: _OrderDir
    limit: int
    offset: int = 0
    anchor: tuple[Any, int] | None = None
    anchor_op: Literal['<', '>'] | None = None


StandardPaginationStateBody = Annotated[
    bytes, Body(media_type='application/x-protobuf')
]

_OrderDir = Literal['asc', 'desc']
_CursorKind = Literal['id', 'datetime', 'text']

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

T = TypeVar('T')


async def sp_render_response(
    template: str,
    context: dict[str, Any],
    state: StandardPaginationState,
) -> Response:
    """
    Render an HTML response and attach the updated StandardPaginationState.

    Keeping this helper in `standard_pagination` makes it hard to forget the header.
    """
    state.DiscardUnknownFields()  # type: ignore
    response = await render_response(template, context)
    response.headers['X-StandardPagination'] = (
        urlsafe_b64encode(state.SerializeToString()).rstrip(b'=').decode()
    )
    return response


def _dt_to_us(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    delta = value.astimezone(UTC) - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


def _us_to_dt(value: int) -> datetime:
    return _EPOCH + timedelta(microseconds=value)


def sp_num_pages(*, num_items: cython.size_t, page_size: cython.size_t) -> int:
    """
    Compute total pages from num_items/page_size.
    Reports at least 1 page (even for empty lists).
    """
    return max(1, _ceil_div(num_items, page_size))


async def sp_paginate_table(
    row_type: type[T],
    sp_state: bytes,
    /,
    *,
    table: LiteralString,
    where: Composable = SQL('TRUE'),
    params: tuple[Any, ...] = (),
    page_size: int,
    cursor_column: LiteralString = 'id',
    id_column: LiteralString = 'id',
    cursor_kind: _CursorKind = 'id',
    order_dir: _OrderDir = 'desc',
    display_dir: _OrderDir | None = None,
    distance: int = STANDARD_PAGINATION_DISTANCE,
) -> tuple[list[T], StandardPaginationState]:
    """
    StandardPagination for a single table.

    This is the standard entrypoint for most endpoints that paginate a table by
    some cursor column (e.g. `created_at`, `updated_at`, `display_name`) with a
    stable snapshot that prevents newly inserted rows from reshuffling results.
    """
    return await sp_paginate_query(
        row_type,
        sp_state,
        select=SQL('*'),
        from_=Identifier(table),
        where=where,
        params=params,
        cursor_key=cursor_column,
        id_key=id_column,
        page_size=page_size,
        cursor_kind=cursor_kind,
        order_dir=order_dir,
        display_dir=display_dir,
        distance=distance,
    )


async def sp_paginate_query(
    _row_type: type[T],
    sp_state: bytes,
    /,
    *,
    select: Composable,
    from_: Composable,
    where: Composable = SQL('TRUE'),
    params: tuple[Any, ...] = (),
    cursor_key: LiteralString,
    id_key: LiteralString,
    page_size: int,
    cursor_sql: Identifier | None = None,
    id_sql: Identifier | None = None,
    cursor_kind: _CursorKind = 'id',
    order_dir: _OrderDir = 'desc',
    display_dir: _OrderDir | None = None,
    distance: int = STANDARD_PAGINATION_DISTANCE,
) -> tuple[list[T], StandardPaginationState]:
    """StandardPagination over an arbitrary FROM clause, ordered by (cursor_sql, id_sql)."""
    if cursor_sql is None:
        cursor_sql = Identifier(cursor_key)
    if id_sql is None:
        id_sql = Identifier(id_key)

    state = StandardPaginationState.FromString(sp_state) if sp_state else None

    cursor_codec = _cursor_codec(cursor_kind)
    expected_variant = cursor_codec.storage
    assert state is None or state.WhichOneof('cursors') == expected_variant, (
        f'StandardPagination: Expected cursor variant {expected_variant!r}, got {state.WhichOneof("cursors")!r}'
    )

    async with db() as conn:
        if state is None:
            snapshot_cursor_raw, snapshot_max_id = await _snapshot(
                conn,
                from_=from_,
                where=where,
                params=params,
                cursor_sql=cursor_sql,
                id_sql=id_sql,
            )

            if snapshot_max_id:
                encoded_snapshot_cursor = cursor_codec.encode(snapshot_cursor_raw)
            else:
                encoded_snapshot_cursor = cursor_codec.empty
                snapshot_cursor_raw = cursor_codec.decode(encoded_snapshot_cursor)

            state = StandardPaginationState(
                current_page=1,
                page_size=page_size,
                snapshot_max_id=snapshot_max_id,
                max_known_page=1,
            )
            if cursor_codec.storage == 'u64':
                state.u64.snapshot = encoded_snapshot_cursor  # type: ignore
            else:
                state.text.snapshot = encoded_snapshot_cursor  # type: ignore

            count_limit = _sp_count_limit(page_size=page_size)
            num_items_limited = await _count_limited(
                conn,
                from_=from_,
                where=where,
                params=params,
                cursor_sql=cursor_sql,
                id_sql=id_sql,
                snapshot=(snapshot_cursor_raw, snapshot_max_id),
                limit=count_limit,
            )

            if num_items_limited < count_limit:
                # Dataset is small enough to know total pages/items
                state.num_items = num_items_limited
                state.num_pages = sp_num_pages(
                    num_items=num_items_limited, page_size=page_size
                )
                state.max_known_page = state.num_pages

        else:
            assert 1 <= state.current_page <= state.max_known_page
            assert state.page_size == page_size

            if state.HasField('num_pages'):
                assert state.num_pages == state.max_known_page
                assert state.HasField('num_items')
            else:
                assert not state.HasField('num_items')

        if state.HasField('requested_page'):
            requested_page = state.requested_page
            state.ClearField('requested_page')
        else:
            requested_page = state.current_page
        assert 1 <= requested_page <= (state.num_pages or state.max_known_page)

        snapshot_max_id = state.snapshot_max_id
        snapshot_cursor_value = cursor_codec.decode(
            state.u64.snapshot if cursor_codec.storage == 'u64' else state.text.snapshot
        )

        plan = _plan(
            state,
            requested_page=requested_page,
            cursor_codec=cursor_codec,
            order_dir=order_dir,
            distance=distance,
        )

        items = await _select_page(
            conn,
            select=select,
            from_=from_,
            where=where,
            params=params,
            cursor_sql=cursor_sql,
            id_sql=id_sql,
            snapshot=(snapshot_cursor_value, snapshot_max_id),
            plan=plan,
        )

        # Normalize rows to the primary order
        if plan.order_dir != order_dir:
            items.reverse()

        state.current_page = requested_page

        if items:
            first = items[0]
            last = items[-1]
            state.page_first_id = first[id_key]
            state.page_last_id = last[id_key]
            encoded_first = cursor_codec.encode(first[cursor_key])
            encoded_last = cursor_codec.encode(last[cursor_key])
            if cursor_codec.storage == 'u64':
                state.u64.page_first = encoded_first  # type: ignore
                state.u64.page_last = encoded_last  # type: ignore
            else:
                state.text.page_first = encoded_first  # type: ignore
                state.text.page_last = encoded_last  # type: ignore
        else:
            state.page_first_id = 0
            state.page_last_id = 0
            if cursor_codec.storage == 'u64':
                state.u64.page_first = 0
                state.u64.page_last = 0
            else:
                state.text.page_first = ''
                state.text.page_last = ''

        if not state.num_pages and items:
            boundary_cursor_encoded = (
                state.u64.page_last
                if cursor_codec.storage == 'u64'
                else state.text.page_last
            )
            remaining_items_limited = await _count_beyond_limited(
                conn,
                from_=from_,
                where=where,
                params=params,
                cursor_sql=cursor_sql,
                id_sql=id_sql,
                snapshot=(snapshot_cursor_value, snapshot_max_id),
                boundary=(
                    cursor_codec.decode(boundary_cursor_encoded),
                    state.page_last_id,
                ),
                boundary_op='<' if order_dir == 'desc' else '>',
                limit=_sp_lookahead_limit(page_size=page_size, distance=distance),
            )
            _update_discovery(
                state,
                current_page_items=len(items),
                remaining_items_limited=remaining_items_limited,
                distance=distance,
            )

    if display_dir is not None and display_dir != order_dir:
        items.reverse()

    return items, state  # type: ignore


def _cursor_codec(kind: _CursorKind) -> _SpCursorCodec:
    if kind == 'id':
        return _SpCursorCodec(
            encode=lambda value: value,
            decode=lambda value: value,
            empty=0,
            storage='u64',
        )
    if kind == 'datetime':
        return _SpCursorCodec(
            encode=lambda value: _dt_to_us(value),
            decode=lambda value: _us_to_dt(value),
            empty=0,
            storage='u64',
        )
    if kind == 'text':
        return _SpCursorCodec(
            encode=lambda value: str(value),
            decode=lambda value: str(value),
            empty='',
            storage='text',
        )
    raise NotImplementedError(f'Unsupported cursor kind {kind!r}')


async def _snapshot(
    conn: AsyncConnection,
    *,
    from_: Composable,
    where: Composable,
    params: tuple[Any, ...],
    cursor_sql: Composable,
    id_sql: Composable,
) -> tuple[Any | None, int]:
    """
    Return snapshot bounds:
    - snapshot_cursor: MAX(cursor_sql) (may be NULL for empty sets)
    - snapshot_max_id: MAX(id_sql) (0 for empty sets)
    """
    query = SQL("""
        SELECT MAX({cursor}), COALESCE(MAX({id}), 0)
        FROM {from_}
        WHERE {where}
    """).format(
        cursor=cursor_sql,
        id=id_sql,
        from_=from_,
        where=where,
    )

    async with await conn.execute(query, params) as r:
        return await r.fetchone()  # type: ignore


def _plan(
    state: StandardPaginationState,
    /,
    *,
    requested_page: int,
    cursor_codec: _SpCursorCodec,
    order_dir: _OrderDir,
    distance: int,
) -> _StandardPaginationQueryPlan:
    """
    Plan a query for a (cursor, id)-ordered collection inside a stable snapshot.

    Page numbering is 1-based in `order_dir` (page 1 is OFFSET 0).

    This prefers:
    - page 1 via OFFSET 0
    - last page (when known) via reverse order + OFFSET 0
    - small jumps around current page using keyset anchors + small OFFSET
    - otherwise fall back to OFFSET from the closest end (when last page known)
    """
    page = requested_page
    page_size = state.page_size
    reverse_dir = _reverse_dir(order_dir)

    if page == 1:
        # Jump to first page directly
        return _StandardPaginationQueryPlan(order_dir=order_dir, limit=page_size)

    num_pages = state.num_pages

    if page == num_pages:
        # Jump to last page directly
        limit = (state.num_items % page_size) or page_size
        return _StandardPaginationQueryPlan(order_dir=reverse_dir, limit=limit)

    current_page = state.current_page
    page_first_id = state.page_first_id
    page_last_id = state.page_last_id

    if page_first_id and page_last_id:
        # Cheap nearby navigation (<= distance) using cursor anchors + small OFFSET
        delta = page - current_page

        if delta > 0 and delta <= distance:
            anchor_id = page_last_id
            anchor_cursor = cursor_codec.decode(
                state.u64.page_last
                if cursor_codec.storage == 'u64'
                else state.text.page_last
            )
            return _StandardPaginationQueryPlan(
                order_dir=order_dir,
                limit=page_size,
                offset=(delta - 1) * page_size,
                anchor=(anchor_cursor, anchor_id),
                anchor_op='<' if order_dir == 'desc' else '>',
            )

        if delta < 0 and -delta <= distance:
            anchor_id = page_first_id
            anchor_cursor = cursor_codec.decode(
                state.u64.page_first
                if cursor_codec.storage == 'u64'
                else state.text.page_first
            )
            return _StandardPaginationQueryPlan(
                order_dir=reverse_dir,
                limit=page_size,
                offset=(-delta - 1) * page_size,
                anchor=(anchor_cursor, anchor_id),
                anchor_op='>' if order_dir == 'desc' else '<',
            )

    # Use OFFSET from one of the ends
    assert 1 <= num_pages <= STANDARD_PAGINATION_MAX_FULL_PAGES
    offset_from_start = (page - 1) * page_size
    offset_from_end = max(0, state.num_items - page * page_size)

    return (
        _StandardPaginationQueryPlan(
            order_dir=order_dir, limit=page_size, offset=offset_from_start
        )
        if offset_from_start <= offset_from_end
        else _StandardPaginationQueryPlan(
            order_dir=reverse_dir, limit=page_size, offset=offset_from_end
        )
    )


async def _select_page(
    conn: AsyncConnection,
    *,
    select: Composable,
    from_: Composable,
    where: Composable,
    params: tuple[Any, ...],
    cursor_sql: Composable,
    id_sql: Composable,
    snapshot: tuple[Any, int],
    plan: _StandardPaginationQueryPlan,
) -> list[dict]:
    snapshot_cursor, snapshot_max_id = snapshot
    if snapshot_max_id <= 0:
        return []

    conditions: list[Composable] = [
        where,
        SQL('{} <= %s').format(id_sql),
        SQL('({}, {}) <= (%s, %s)').format(cursor_sql, id_sql),
    ]
    query_params: list[Any] = [
        *params,
        snapshot_max_id,
        snapshot_cursor,
        snapshot_max_id,
    ]

    if plan.anchor is not None:
        assert plan.anchor_op is not None
        conditions.append(
            SQL('({}, {}) {} (%s, %s)').format(cursor_sql, id_sql, SQL(plan.anchor_op))
        )
        query_params.extend(plan.anchor)

    query = SQL("""
        SELECT {select} FROM {from_}
        WHERE {conditions}
        ORDER BY {cursor} {dir}, {id} {dir}
        OFFSET %s LIMIT %s
    """).format(
        select=select,
        from_=from_,
        conditions=SQL(' AND ').join(conditions),
        cursor=cursor_sql,
        id=id_sql,
        dir=_order_dir_sql(plan.order_dir),
    )
    query_params.extend((plan.offset, plan.limit))

    async with (
        await conn.cursor(row_factory=dict_row).execute(query, query_params) as r,
    ):
        return await r.fetchall()


async def _count_limited(
    conn: AsyncConnection,
    *,
    from_: Composable,
    where: Composable,
    params: tuple[Any, ...],
    cursor_sql: Composable,
    id_sql: Composable,
    snapshot: tuple[Any, int],
    limit: int,
) -> int:
    """Count rows inside the snapshot, capped by `limit`."""
    snapshot_cursor, snapshot_max_id = snapshot
    if snapshot_max_id <= 0:
        return 0

    query = SQL("""
        SELECT COUNT(*) FROM (
            SELECT 1 FROM {from_}
            WHERE {where}
              AND {id} <= %s
              AND ({cursor}, {id}) <= (%s, %s)
            LIMIT %s
        ) AS subquery
    """).format(
        from_=from_,
        where=where,
        cursor=cursor_sql,
        id=id_sql,
    )
    params = (
        *params,
        snapshot_max_id,
        snapshot_cursor,
        snapshot_max_id,
        limit,
    )

    async with await conn.execute(query, params) as r:
        return (await r.fetchone())[0]  # type: ignore


async def _count_beyond_limited(
    conn: AsyncConnection,
    *,
    from_: Composable,
    where: Composable,
    params: tuple[Any, ...],
    cursor_sql: Composable,
    id_sql: Composable,
    snapshot: tuple[Any, int],
    boundary: tuple[Any, int],
    boundary_op: Literal['<', '>'],
    limit: int,
) -> int:
    """
    Count rows beyond the page boundary inside the snapshot, capped by `limit`.
    `boundary_op` defines the direction: use '<' or '>' against `boundary`.
    """
    snapshot_cursor, snapshot_max_id = snapshot
    if snapshot_max_id <= 0:
        return 0

    boundary_cursor, boundary_id = boundary
    query = SQL("""
        SELECT COUNT(*) FROM (
            SELECT 1 FROM {from_}
            WHERE {where}
              AND {id} <= %s
              AND ({cursor}, {id}) <= (%s, %s)
              AND ({cursor}, {id}) {op} (%s, %s)
            LIMIT %s
        ) AS subquery
    """).format(
        from_=from_,
        where=where,
        cursor=cursor_sql,
        id=id_sql,
        op=SQL(boundary_op),
    )
    params = (
        *params,
        snapshot_max_id,
        snapshot_cursor,
        snapshot_max_id,
        boundary_cursor,
        boundary_id,
        limit,
    )

    async with await conn.execute(query, params) as r:
        return (await r.fetchone())[0]  # type: ignore


def _update_discovery(
    state: StandardPaginationState,
    /,
    *,
    current_page_items: int,
    remaining_items_limited: int,
    distance: cython.size_t = STANDARD_PAGINATION_DISTANCE,
) -> None:
    """
    Update discovery fields (`max_known_page`, and optionally `num_pages`/`num_items`)
    based on a limited count of remaining items beyond the current page.
    """
    if state.HasField('num_pages'):
        return

    page_size = state.page_size
    current_page = state.current_page
    remaining = remaining_items_limited

    # End is at current page
    if remaining == 0:
        state.num_pages = current_page
        state.num_items = (current_page - 1) * page_size + current_page_items
        state.max_known_page = current_page
        return

    # End is within lookahead distance (exact)
    if remaining < _sp_lookahead_limit(page_size=page_size, distance=distance):
        additional_pages = _ceil_div(remaining, page_size)
        last_page = current_page + additional_pages
        last_page_size = (remaining % page_size) or page_size

        state.num_pages = last_page
        state.num_items = (last_page - 1) * page_size + last_page_size
        state.max_known_page = last_page
        return

    # End is beyond lookahead distance
    state.max_known_page = max(state.max_known_page, current_page + distance)


@cython.cfunc
def _sp_count_limit(
    *,
    page_size: cython.size_t,
    STANDARD_PAGINATION_COUNT_MAX_PAGES: cython.size_t = STANDARD_PAGINATION_COUNT_MAX_PAGES,
) -> int:
    """Cap COUNT(*) to (N pages * page_size) + 1 rows."""
    return STANDARD_PAGINATION_COUNT_MAX_PAGES * page_size + 1


@cython.cfunc
def _sp_lookahead_limit(*, page_size: cython.size_t, distance: cython.size_t) -> int:
    """Probe at most (distance pages * page_size) + 1 rows beyond the current page."""
    return distance * page_size + 1


@cython.cfunc
def _ceil_div(a: cython.size_t, b: cython.size_t) -> cython.size_t:
    return (a + b - 1) // b


@cython.cfunc
def _reverse_dir(value: _OrderDir) -> _OrderDir:
    return 'desc' if value == 'asc' else 'asc'


@cython.cfunc
def _order_dir_sql(value: _OrderDir) -> SQL:
    return SQL('ASC') if value == 'asc' else SQL('DESC')
