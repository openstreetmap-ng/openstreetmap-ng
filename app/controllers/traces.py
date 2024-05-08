from typing import Annotated

import cython
from anyio import create_task_group
from fastapi import APIRouter, Path, Query
from sqlalchemy.orm import joinedload
from starlette import status
from starlette.responses import RedirectResponse

from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.lib.statement_context import options_context
from app.limits import TRACE_TAG_MAX_LENGTH
from app.models.db.trace_ import Trace
from app.models.db.user import User
from app.repositories.trace_point_repository import TracePointRepository
from app.repositories.trace_repository import TraceRepository
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/traces')


@cython.cfunc
async def _get_traces_data(
    *,
    personal: bool,
    tag: str | None,
    after: int | None,
    before: int | None,
) -> dict:
    with options_context(joinedload(Trace.user)):
        traces = await TraceRepository.find_many_recent(
            personal=personal,
            tag=tag,
            after=after,
            before=before,
            limit=30,
        )

    new_after: int | None = None
    new_before: int | None = None

    async def resolve_task():
        await TracePointRepository.resolve_image_coords(traces, limit_per_trace=100, resolution=100)

    async def new_after_task():
        nonlocal new_after
        after = traces[0].id
        after_traces = await TraceRepository.find_many_recent(
            personal=personal,
            tag=tag,
            after=after,
            limit=1,
        )
        if after_traces:
            new_after = after

    async def new_before_task():
        nonlocal new_before
        before = traces[-1].id
        before_traces = await TraceRepository.find_many_recent(
            personal=personal,
            tag=tag,
            before=before,
            limit=1,
        )
        if before_traces:
            new_before = before

    if traces:
        async with create_task_group() as tg:
            tg.start_soon(resolve_task)
            tg.start_soon(new_after_task)
            tg.start_soon(new_before_task)

    base_url = '/traces/mine' if personal else '/traces'
    base_url_notag = base_url
    if tag is not None:
        base_url += f'/tag/{tag}'

    image_coords = JSON_ENCODE(tuple(trace.image_coords for trace in traces)).decode()

    return {
        'personal': personal,
        'base_url': base_url,
        'base_url_notag': base_url_notag,
        'tag': tag,
        'new_after': new_after,
        'new_before': new_before,
        'traces': traces,
        'image_coords': image_coords,
    }


@router.get('/')
async def index(
    after: Annotated[int | None, Query(gt=0)] = None,
    before: Annotated[int | None, Query(gt=0)] = None,
):
    data = await _get_traces_data(personal=False, tag=None, after=after, before=before)
    return render_response('traces/index.jinja2', data)


@router.get('/tag/{tag:str}')
async def tagged(
    tag: Annotated[str, Path(min_length=1, max_length=TRACE_TAG_MAX_LENGTH)],
    after: Annotated[int | None, Query(gt=0)] = None,
    before: Annotated[int | None, Query(gt=0)] = None,
):
    data = await _get_traces_data(personal=False, tag=tag, after=after, before=before)
    return render_response('traces/index.jinja2', data)


@router.get('/mine')
async def mine(
    _: Annotated[User, web_user()],
    after: Annotated[int | None, Query(gt=0)] = None,
    before: Annotated[int | None, Query(gt=0)] = None,
):
    data = await _get_traces_data(personal=True, tag=None, after=after, before=before)
    return render_response('traces/mine.jinja2', data)


@router.get('/mine/tag/{tag:str}')
async def mine_tagged(
    _: Annotated[User, web_user()],
    tag: Annotated[str, Path(min_length=1, max_length=TRACE_TAG_MAX_LENGTH)],
    after: Annotated[int | None, Query(gt=0)] = None,
    before: Annotated[int | None, Query(gt=0)] = None,
):
    data = await _get_traces_data(personal=True, tag=tag, after=after, before=before)
    return render_response('traces/mine.jinja2', data)


@router.get('/new')
async def legacy_new():
    return RedirectResponse('/trace/upload', status.HTTP_301_MOVED_PERMANENTLY)
