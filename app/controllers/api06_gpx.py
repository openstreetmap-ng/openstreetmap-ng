from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from pydantic import NonNegativeInt

from app.config import TRACE_POINT_QUERY_AREA_MAX_SIZE, TRACE_POINT_QUERY_DEFAULT_LIMIT
from app.format import Format06
from app.format.gpx import FormatGPX
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.lib.xml_body import xml_body
from app.models.db.trace import TraceVisibility
from app.models.db.user import User
from app.models.types import TraceId
from app.queries.trace_query import TraceQuery
from app.queries.user_query import UserQuery
from app.responses.osm_response import GPXResponse
from app.services.trace_service import TraceService

router = APIRouter(prefix='/api/0.6')


@router.post('/gpx')
@router.post('/gpx/create')
async def upload_trace(
    _: Annotated[User, api_user('write_gpx')],
    file: Annotated[UploadFile, File()],
    description: Annotated[str, Form()],
    tags: Annotated[str, Form()] = '',
    visibility: Annotated[TraceVisibility | None, Form()] = None,
    public: Annotated[int, Form(deprecated=True)] = 0,
):
    if visibility is None:
        # Backwards compatibility:
        # if public (numeric) is non-zero, set visibility to public
        visibility = 'public' if public else 'private'

    trace_id = await TraceService.upload(
        file,
        description=description,
        tags=tags,
        visibility=visibility,
    )
    return Response(str(trace_id), media_type='text/plain')


@router.get('/gpx/{trace_id:int}')
@router.get('/gpx/{trace_id:int}.xml')
@router.get('/gpx/{trace_id:int}/details')
@router.get('/gpx/{trace_id:int}/details.xml')
async def get_trace(
    trace_id: TraceId,
):
    trace = await TraceQuery.get_one_by_id(trace_id)

    async with TaskGroup() as tg:
        items = [trace]
        tg.create_task(UserQuery.resolve_users(items))
        tg.create_task(TraceQuery.resolve_coords(items, limit_per_trace=1, resolution=None))

    return Format06.encode_gpx_file(trace)


@router.get('/user/gpx_files')
@router.get('/user/gpx_files.xml')
async def get_current_user_traces(
    user: Annotated[User, api_user('read_gpx')],
):
    traces = await TraceQuery.find_many_recent(user_id=user['id'], limit=None)

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(traces))
        tg.create_task(TraceQuery.resolve_coords(traces, limit_per_trace=1, resolution=None))

    return Format06.encode_gpx_files(traces)


@router.get('/gpx/{trace_id:int}/data.xml')
@router.get('/gpx/{trace_id:int}/data.gpx')
async def get_trace_gpx(
    trace_id: TraceId,
):
    trace = await TraceQuery.get_one_by_id(trace_id)
    data = FormatGPX.encode_track(trace)
    resp = GPXResponse.serialize(data)
    return Response(
        content=resp.body,
        status_code=resp.status_code,
        headers={**resp.headers, 'Content-Disposition': f'attachment; filename="{trace_id}.gpx"'},
        media_type=resp.media_type,
    )


@router.get('/gpx/{trace_id:int}/data')
async def download_trace(
    trace_id: TraceId,
):
    content = await TraceQuery.get_one_data_by_id(trace_id)
    return Response(
        content=content,
        # Intentionally not using trace.name here.
        # It's unsafe and difficult to make right, removing in API 0.7
        headers={'Content-Disposition': f'attachment; filename="{trace_id}"'},
    )


@router.put('/gpx/{trace_id:int}')
async def update_trace(
    trace_id: TraceId,
    data: Annotated[list[dict], xml_body('osm/gpx_file')],
    _: Annotated[User, api_user('write_gpx')],
):
    try:
        trace = Format06.decode_gpx_file(data[0])
    except Exception as e:
        raise_for.bad_xml('trace', str(e))

    await TraceService.update(
        trace_id,
        name=trace['name'],
        description=trace['description'],
        tags=trace['tags'],
        visibility=trace['visibility'],
    )
    return Response()


@router.delete('/gpx/{trace_id:int}')
async def delete_trace(
    trace_id: TraceId,
    _: Annotated[User, api_user('write_gpx')],
):
    await TraceService.delete(trace_id)
    return Response()


@router.get('/trackpoints', response_class=GPXResponse)
@router.get('/trackpoints.gpx', response_class=GPXResponse)
async def trackpoints(
    bbox: Annotated[str, Query()],
    page_number: Annotated[NonNegativeInt, Query(alias='pageNumber')] = 0,
):
    geometry = parse_bbox(bbox)
    if geometry.area > TRACE_POINT_QUERY_AREA_MAX_SIZE:
        raise_for.trace_points_query_area_too_big()

    async def public_task():
        return await TraceQuery.find_many_by_geometry(
            geometry,
            identifiable_trackable=True,
            limit=TRACE_POINT_QUERY_DEFAULT_LIMIT,
            legacy_offset=page_number * TRACE_POINT_QUERY_DEFAULT_LIMIT,
        )

    async def private_task():
        return await TraceQuery.find_many_by_geometry(
            geometry,
            identifiable_trackable=False,
            limit=TRACE_POINT_QUERY_DEFAULT_LIMIT,
            legacy_offset=page_number * TRACE_POINT_QUERY_DEFAULT_LIMIT,
        )

    async with TaskGroup() as tg:
        public_t = tg.create_task(public_task())
        private_t = tg.create_task(private_task())

    return FormatGPX.encode_tracks([*public_t.result(), *private_t.result()])
