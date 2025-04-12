from asyncio import TaskGroup
from typing import Annotated

import cython
from fastapi import APIRouter, Path, Query
from polyline_rs import encode_lonlat
from starlette import status
from starlette.responses import RedirectResponse

from app.config import TRACES_LIST_PAGE_SIZE
from app.lib.auth_context import auth_user, web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.models.types import DisplayName, TraceId
from app.queries.trace_query import TraceQuery
from app.queries.user_query import UserQuery

router = APIRouter()


@router.get('/traces')
async def index(
    after: Annotated[TraceId | None, Query()] = None,
    before: Annotated[TraceId | None, Query()] = None,
):
    data = await _get_data(user=None, tag=None, after=after, before=before)
    return await render_response('traces/index', data)


@router.get('/traces/tag/{tag:str}')
async def tagged(
    tag: Annotated[str, Path(min_length=1)],
    after: Annotated[TraceId | None, Query()] = None,
    before: Annotated[TraceId | None, Query()] = None,
):
    data = await _get_data(user=None, tag=tag, after=after, before=before)
    return await render_response('traces/index', data)


@router.get('/user/{display_name:str}/traces')
async def personal(
    display_name: Annotated[DisplayName, Path(min_length=1)],
    after: Annotated[TraceId | None, Query()] = None,
    before: Annotated[TraceId | None, Query()] = None,
):
    user = await UserQuery.find_one_by_display_name(display_name)
    data = await _get_data(user=user, tag=None, after=after, before=before)
    return await render_response('traces/index', data)


@router.get('/user/{display_name:str}/traces/tag/{tag:str}')
async def personal_tagged(
    display_name: Annotated[DisplayName, Path(min_length=1)],
    tag: Annotated[str, Path(min_length=1)],
    after: Annotated[TraceId | None, Query()] = None,
    before: Annotated[TraceId | None, Query()] = None,
):
    user = await UserQuery.find_one_by_display_name(display_name)
    data = await _get_data(user=user, tag=tag, after=after, before=before)
    return await render_response('traces/index', data)


@router.get('/user/{_:str}/traces/{trace_id:int}')
async def legacy_personal_details(_, trace_id: TraceId):
    return RedirectResponse(f'/trace/{trace_id}', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/traces/mine{suffix:path}')
async def legacy_mine(
    user: Annotated[User, web_user()],
    suffix: str,
):
    return RedirectResponse(f'/user/{user["display_name"]}/traces{suffix}', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/traces/new')
async def legacy_new():
    return RedirectResponse('/trace/upload', status.HTTP_301_MOVED_PERMANENTLY)


async def _get_data(
    *,
    user: User | None,
    tag: str | None,
    after: TraceId | None,
    before: TraceId | None,
) -> dict:
    user_id = user['id'] if user is not None else None
    traces = await TraceQuery.find_many_recent(
        user_id=user_id,
        tag=tag,
        after=after,
        before=before,
        limit=TRACES_LIST_PAGE_SIZE,
    )

    async def new_after_task():
        after = traces[0]['id']
        after_traces = await TraceQuery.find_many_recent(
            user_id=user_id,
            tag=tag,
            after=after,
            limit=1,
        )
        return after if after_traces else None

    async def new_before_task():
        before = traces[-1]['id']
        before_traces = await TraceQuery.find_many_recent(
            user_id=user_id,
            tag=tag,
            before=before,
            limit=1,
        )
        return before if before_traces else None

    if traces:
        async with TaskGroup() as tg:
            tg.create_task(UserQuery.resolve_users(traces))
            tg.create_task(TraceQuery.resolve_coords(traces, limit_per_trace=100, resolution=90))
            new_after_t = tg.create_task(new_after_task())
            new_before_t = tg.create_task(new_before_task())

        traces_lines = ';'.join(encode_lonlat(trace['coords'].tolist(), 0) for trace in traces)  # type: ignore
        new_after = new_after_t.result()
        new_before = new_before_t.result()
    else:
        traces_lines = ''
        new_after = None
        new_before = None

    base_url = f'/user/{user["display_name"]}/traces' if user is not None else '/traces'
    base_url_notag = base_url
    if tag is not None:
        base_url += f'/tag/{tag}'

    active_tab = _get_active_tab(user)

    return {
        'profile': user,
        'active_tab': active_tab,
        'base_url': base_url,
        'base_url_notag': base_url_notag,
        'tag': tag,
        'new_after': new_after,
        'new_before': new_before,
        'traces': traces,
        'traces_lines': traces_lines,
    }


@cython.cfunc
def _get_active_tab(user: User | None) -> int:
    """Get the active tab number for the traces page."""
    if user is not None:
        current_user = auth_user()
        if current_user is not None and user['id'] == current_user['id']:
            return 1  # viewing own traces
        return 2  # viewing other user's traces

    return 0  # viewing public traces
