from typing import Annotated

from anyio import create_task_group
from fastapi import APIRouter, Query

from app.lib.render_response import render_response
from app.lib.statement_context import joinedload_context
from app.models.db.trace_ import Trace
from app.repositories.trace_point_repository import TracePointRepository
from app.repositories.trace_repository import TraceRepository
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/traces')


@router.get('/')
async def index(
    after: Annotated[int | None, Query(gt=0)] = None,
    before: Annotated[int | None, Query(gt=0)] = None,
):
    with joinedload_context(Trace.user):
        traces = await TraceRepository.find_many_recent(after=after, before=before, limit=30)

    new_after: int | None = None
    new_before: int | None = None

    async def resolve_task():
        await TracePointRepository.resolve_image_coords(traces, limit_per_trace=50)

    async def new_after_task():
        nonlocal new_after
        after = traces[0].id
        after_traces = await TraceRepository.find_many_recent(after=after, limit=1)
        if after_traces:
            new_after = after

    async def new_before_task():
        nonlocal new_before
        before = traces[-1].id
        before_traces = await TraceRepository.find_many_recent(before=before, limit=1)
        if before_traces:
            new_before = before

    if traces:
        async with create_task_group() as tg:
            tg.start_soon(resolve_task)
            tg.start_soon(new_after_task)
            tg.start_soon(new_before_task)

    image_coords = JSON_ENCODE(tuple(trace.image_coords for trace in traces)).decode()
    return render_response(
        'traces/index.jinja2',
        {
            'new_after': new_after,
            'new_before': new_before,
            'traces': traces,
            'image_coords': image_coords,
        },
    )
