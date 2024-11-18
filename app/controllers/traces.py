from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Path, Query
from polyline_rs import encode_lonlat
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import auth_user, web_user
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.limits import DISPLAY_NAME_MAX_LENGTH, TRACE_TAG_MAX_LENGTH, TRACES_LIST_PAGE_SIZE
from app.models.db.trace_ import Trace
from app.models.db.user import User
from app.models.types import DisplayNameType
from app.queries.trace_query import TraceQuery
from app.queries.trace_segment_query import TraceSegmentQuery
from app.queries.user_query import UserQuery

router = APIRouter()


async def _get_traces_data(
    *,
    user: User | None,
    tag: str | None,
    after: int | None,
    before: int | None,
) -> dict:
    user_id = user.id if (user is not None) else None

    with options_context(
        joinedload(Trace.user).load_only(
            User.id,
            User.display_name,
            User.avatar_type,
            User.avatar_id,
        )
    ):
        traces = await TraceQuery.find_many_recent(
            user_id=user_id,
            tag=tag,
            after=after,
            before=before,
            limit=TRACES_LIST_PAGE_SIZE,
        )

    async def new_after_task():
        after = traces[0].id
        after_traces = await TraceQuery.find_many_recent(
            user_id=user_id,
            tag=tag,
            after=after,
            limit=1,
        )
        return after if after_traces else None

    async def new_before_task():
        before = traces[-1].id
        before_traces = await TraceQuery.find_many_recent(
            user_id=user_id,
            tag=tag,
            before=before,
            limit=1,
        )
        return before if before_traces else None

    if traces:
        async with TaskGroup() as tg:
            tg.create_task(TraceSegmentQuery.resolve_coords(traces, limit_per_trace=100, resolution=90))
            new_after_t = tg.create_task(new_after_task())
            new_before_t = tg.create_task(new_before_task())
        traces_lines = ';'.join(encode_lonlat(trace.coords.tolist(), 0) for trace in traces)
        new_after = new_after_t.result()
        new_before = new_before_t.result()
    else:
        traces_lines = ''
        new_after = None
        new_before = None

    base_url = f'/user/{user.display_name}/traces' if (user is not None) else '/traces'
    base_url_notag = base_url
    if tag is not None:
        base_url += f'/tag/{tag}'

    if user is None:
        active_tab = 0  # viewing public traces
    else:
        current_user = auth_user()
        if (current_user is not None) and user.id == current_user.id:
            active_tab = 1  # viewing own traces
        else:
            active_tab = 2  # viewing other user's traces

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


@router.get('/traces')
async def index(
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    data = await _get_traces_data(user=None, tag=None, after=after, before=before)
    return await render_response('traces/index.jinja2', data)


@router.get('/traces/tag/{tag:str}')
async def tagged(
    tag: Annotated[str, Path(min_length=1, max_length=TRACE_TAG_MAX_LENGTH)],
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    data = await _get_traces_data(user=None, tag=tag, after=after, before=before)
    return await render_response('traces/index.jinja2', data)


@router.get('/user/{display_name:str}/traces')
async def personal(
    display_name: Annotated[DisplayNameType, Path(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)],
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    user = await UserQuery.find_one_by_display_name(display_name)
    data = await _get_traces_data(user=user, tag=None, after=after, before=before)
    return await render_response('traces/index.jinja2', data)


@router.get('/user/{display_name:str}/traces/tag/{tag:str}')
async def personal_tagged(
    display_name: Annotated[DisplayNameType, Path(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)],
    tag: Annotated[str, Path(min_length=1, max_length=TRACE_TAG_MAX_LENGTH)],
    after: Annotated[PositiveInt | None, Query()] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    user = await UserQuery.find_one_by_display_name(display_name)
    data = await _get_traces_data(user=user, tag=tag, after=after, before=before)
    return await render_response('traces/index.jinja2', data)


@router.get('/traces/mine')
async def legacy_mine(
    user: Annotated[User, web_user()],
):
    return RedirectResponse(f'/user/{user.display_name}/traces', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/traces/mine/tag/{tag:str}')
async def legacy_mine_tagged(
    user: Annotated[User, web_user()],
    tag: Annotated[str, Path(min_length=1, max_length=TRACE_TAG_MAX_LENGTH)],
):
    return RedirectResponse(f'/user/{user.display_name}/traces/tag/{tag}', status.HTTP_301_MOVED_PERMANENTLY)


@router.get('/traces/new')
async def legacy_new():
    return RedirectResponse('/trace/upload', status.HTTP_301_MOVED_PERMANENTLY)
