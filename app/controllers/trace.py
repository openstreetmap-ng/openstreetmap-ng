from typing import Annotated

from fastapi import APIRouter, Response
from polyline_rs import encode_lonlat
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload
from starlette import status
from starlette.responses import RedirectResponse

from app.config import API_URL
from app.lib.auth_context import web_user
from app.lib.options_context import options_context
from app.lib.render_response import render_response
from app.models.db.trace_ import Trace
from app.models.db.user import User
from app.queries.trace_query import TraceQuery
from app.queries.trace_segment_query import TraceSegmentQuery

# TODO: legacy traces url: user profiles
router = APIRouter(prefix='/trace')


@router.get('/upload')
async def upload(_: Annotated[User, web_user()]):
    return await render_response('traces/upload.jinja2')


@router.get('/{trace_id:int}')
async def details(trace_id: PositiveInt):
    with options_context(joinedload(Trace.user)):
        trace = await TraceQuery.get_one_by_id(trace_id)
    await TraceSegmentQuery.resolve_coords((trace,), limit_per_trace=500, resolution=None)
    trace_line = encode_lonlat(trace.coords.tolist(), 6)
    return await render_response('traces/details.jinja2', {'trace': trace, 'trace_line': trace_line})


@router.get('/{trace_id:int}/edit')
async def edit(trace_id: PositiveInt, user: Annotated[User, web_user()]):
    with options_context(joinedload(Trace.user)):
        trace = await TraceQuery.get_one_by_id(trace_id)
    if trace.user_id != user.id:
        # TODO: this could be nicer?
        return Response(None, status.HTTP_403_FORBIDDEN)
    await TraceSegmentQuery.resolve_coords((trace,), limit_per_trace=500, resolution=None)
    trace_line = encode_lonlat(trace.coords.tolist(), 6)
    return await render_response('traces/edit.jinja2', {'trace': trace, 'trace_line': trace_line})


@router.get('/{trace_id:int}/data{suffix:path}')
async def legacy_data(trace_id: PositiveInt, suffix: str):
    return RedirectResponse(f'{API_URL}/api/0.6/gpx/{trace_id}/data{suffix}', status.HTTP_302_FOUND)
