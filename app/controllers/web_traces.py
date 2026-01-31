from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Form, Query, UploadFile
from polyline_rs import encode_lonlat
from psycopg.sql import SQL

from app.config import TRACES_LIST_PAGE_SIZE
from app.exceptions.api_error import APIError
from app.lib.auth_context import auth_scopes, auth_user, web_user
from app.lib.standard_feedback import StandardFeedback
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_paginate_table,
    sp_render_response,
)
from app.models.db.trace import (
    Trace,
    TraceVisibility,
    validate_trace_tags,
)
from app.models.db.user import User
from app.models.types import TraceId, UserId
from app.queries.trace_query import TraceQuery
from app.queries.user_query import UserQuery
from app.services.trace_service import TraceService
from app.utils import id_response

router = APIRouter(prefix='/api/web/traces')


@router.post('/upload')
async def upload(
    _: Annotated[User, web_user()],
    file: Annotated[UploadFile, Form()],
    description: Annotated[str, Form()],
    visibility: Annotated[TraceVisibility, Form()],
    tags: Annotated[list[str] | None, Form()] = None,
):
    try:
        trace_id = await TraceService.upload(
            file, description=description, tags=tags, visibility=visibility
        )
    except* APIError as exc:
        # convert api errors to standard feedback errors
        detail = next(e.detail for e in exc.exceptions if isinstance(e, APIError))
        StandardFeedback.raise_error(None, detail, exc=exc)

    return id_response(trace_id)


@router.post('/{trace_id:int}/update')
async def update(
    _: Annotated[User, web_user()],
    trace_id: TraceId,
    name: Annotated[str, Form()],
    description: Annotated[str, Form()],
    visibility: Annotated[TraceVisibility, Form()],
    tags: Annotated[list[str] | None, Form()] = None,
):
    try:
        await TraceService.update(
            trace_id,
            name=name,
            description=description,
            tags=validate_trace_tags(tags),
            visibility=visibility,
        )
    except* APIError as exc:
        # convert api errors to standard feedback errors
        detail = next(e.detail for e in exc.exceptions if isinstance(e, APIError))
        StandardFeedback.raise_error(None, detail, exc=exc)

    return id_response(trace_id)


@router.post('/{trace_id:int}/delete')
async def delete(
    user: Annotated[User, web_user()],
    trace_id: TraceId,
):
    try:
        await TraceService.delete(trace_id)
    except* APIError as exc:
        # convert api errors to standard feedback errors
        detail = next(e.detail for e in exc.exceptions if isinstance(e, APIError))
        StandardFeedback.raise_error(None, detail, exc=exc)

    return {'redirect_url': f'/user/{user["display_name"]}/traces'}


@router.post('/page')
async def traces_page(
    user_id: Annotated[UserId | None, Query()] = None,
    tag: Annotated[str | None, Query(min_length=1)] = None,
    sp_state: StandardPaginationStateBody = b'',
):
    """
    StandardPagination endpoint for trace listings.

    Supports:
    - public traces (`user_id` omitted)
    - user traces (`user_id` provided, respecting visibility)
    - optional tag filter
    """
    conditions = []
    params = []

    # If unauthenticated, find public traces
    user = auth_user()
    if user is None or user['id'] != user_id or 'read_gpx' not in auth_scopes():
        conditions.append(SQL("visibility IN ('identifiable', 'public')"))

    if user_id is not None:
        conditions.append(SQL('user_id = %s'))
        params.append(user_id)

    if tag is not None:
        conditions.append(SQL('tags @> ARRAY[%s]'))
        params.append(tag)

    traces, state = await sp_paginate_table(
        Trace,
        sp_state,
        table='trace',
        # TODO: support 3.14 Templates
        where=SQL(' AND ').join(conditions) if conditions else SQL('TRUE'),  # type: ignore
        params=tuple(params),
        page_size=TRACES_LIST_PAGE_SIZE,
        cursor_column='id',
        cursor_kind='id',
        order_dir='desc',
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(traces))
        tg.create_task(
            TraceQuery.resolve_coords(traces, limit_per_trace=100, resolution=90)
        )

    traces_lines = (
        ';'.join(
            encode_lonlat(trace['coords'].tolist(), 0)  # type: ignore
            for trace in traces
        )
        if traces
        else ''
    )

    base_url_notag = f'/user-id/{user_id}/traces' if user_id is not None else '/traces'
    return await sp_render_response(
        'traces/page',
        {
            'base_url_notag': base_url_notag,
            'traces': traces,
            'traces_lines': traces_lines,
        },
        state,
    )
