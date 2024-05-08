from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.format06 import Format06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.statement_context import options_context
from app.lib.xml_body import xml_body
from app.models.db.trace_ import Trace
from app.models.db.user import User
from app.models.scope import Scope
from app.models.str import Str255
from app.models.trace_visibility import TraceVisibility
from app.repositories.trace_point_repository import TracePointRepository
from app.repositories.trace_repository import TraceRepository
from app.responses.osm_response import GPXResponse
from app.services.trace_service import TraceService

router = APIRouter()


@router.post('/gpx/create')
async def gpx_create(
    _: Annotated[User, api_user(Scope.write_gpx)],
    file: Annotated[UploadFile, File()],
    description: Annotated[Str255, Form()],
    tags: Annotated[str, Form()] = '',
    visibility: Annotated[TraceVisibility | None, Form()] = None,
    public: Annotated[int, Form(deprecated=True)] = 0,
):
    if visibility is None:
        # backwards compatibility:
        # if public (numeric) is non-zero, set visibility to public
        visibility = 'public' if public else 'private'

    trace = await TraceService.upload(file, description=description, tags=tags, visibility=visibility)
    return Response(str(trace.id), media_type='text/plain')


@router.get('/gpx/{trace_id:int}')
@router.get('/gpx/{trace_id:int}.xml')
@router.get('/gpx/{trace_id:int}/details')
@router.get('/gpx/{trace_id:int}/details.xml')
async def gpx_read(
    trace_id: PositiveInt,
):
    with options_context(joinedload(Trace.user)):
        trace = await TraceRepository.get_one_by_id(trace_id)
    return Format06.encode_gpx_file(trace)


@router.get('/gpx/{trace_id:int}/data.xml')
@router.get('/gpx/{trace_id:int}/data.gpx')
async def gpx_read_data(
    trace_id: PositiveInt,
):
    # ensures that user has access to the trace
    trace = await TraceRepository.get_one_by_id(trace_id)
    trace_points = await TracePointRepository.get_many_by_trace_id(trace_id)
    data = Format06.encode_track(trace_points, trace)
    resp = GPXResponse.serialize(data)
    return Response(
        content=resp.body,
        status_code=resp.status_code,
        headers={**resp.headers, 'Content-Disposition': f'attachment; filename="{trace_id}.gpx"'},
        media_type=resp.media_type,
    )


@router.get('/gpx/{trace_id:int}/data')
async def gpx_read_data_raw(
    trace_id: PositiveInt,
):
    content = await TraceRepository.get_one_data_by_id(trace_id)
    return Response(
        content=content,
        # intentionally not using trace.name here, it's unsafe and difficult to make right, removing in API 0.7
        headers={'Content-Disposition': f'attachment; filename="{trace_id}"'},
    )


@router.put('/gpx/{trace_id:int}')
async def gpx_update(
    trace_id: PositiveInt,
    data: Annotated[dict, xml_body('osm/gpx_file')],
    _: Annotated[User, api_user(Scope.write_gpx)],
):
    try:
        trace = Format06.decode_gpx_file(data)
    except Exception as e:
        raise_for().bad_xml('trace', str(e))

    await TraceService.update(
        trace_id,
        name=trace.name,
        description=trace.description,
        tag_string=trace.tag_string,
        visibility=trace.visibility,
    )
    return Response()


@router.delete('/gpx/{trace_id:int}')
async def gpx_delete(
    trace_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_gpx)],
):
    await TraceService.delete(trace_id)
    return Response()
