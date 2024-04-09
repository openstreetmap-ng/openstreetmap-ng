import logging
from typing import Annotated

import magic
from fastapi import APIRouter, File, Form, Response, UploadFile
from pydantic import PositiveInt

from app.format06 import Format06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.statement_context import joinedload_context
from app.lib.xml_body import xml_body
from app.models.db.trace_ import Trace
from app.models.db.trace_point import TracePoint
from app.models.db.user import User
from app.models.scope import Scope
from app.models.str import Str255
from app.models.trace_visibility import TraceVisibility
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

    trace = await TraceService.upload(file, description, tags, visibility)
    return Response(str(trace.id), media_type='text/plain')


@router.get('/gpx/{trace_id:int}')
@router.get('/gpx/{trace_id:int}.xml')
@router.get('/gpx/{trace_id:int}/details')
@router.get('/gpx/{trace_id:int}/details.xml')
async def gpx_read(
    trace_id: PositiveInt,
):
    with joinedload_context(Trace.user):
        trace = await TraceRepository.get_one_by_id(trace_id)
    return Format06.encode_gpx_file(trace)


@router.get('/gpx/{trace_id:int}/data.xml', response_class=GPXResponse)
@router.get('/gpx/{trace_id:int}/data.gpx', response_class=GPXResponse)
async def gpx_read_data(
    trace_id: PositiveInt,
):
    with joinedload_context(TracePoint.trace):
        trace_points = await TraceRepository.get_one_by_id(trace_id)
    return Format06.encode_track(trace_points)


@router.get('/gpx/{trace_id:int}/data')
async def gpx_read_data_raw(
    trace_id: PositiveInt,
):
    filename, file = await TraceRepository.get_one_data_by_id(trace_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    if content_type == 'text/xml':
        content_type = 'application/gpx+xml'
    logging.debug('Downloading trace file content type is %r', content_type)
    return Response(
        content=file,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        media_type=content_type,
    )


@router.put('/gpx/{trace_id:int}')
async def gpx_update(
    trace_id: PositiveInt,
    data: Annotated[dict, xml_body('osm/gpx_file')],
    _: Annotated[User, api_user(Scope.write_gpx)],
):
    try:
        new_trace = Format06.decode_gpx_file(data)
    except Exception as e:
        raise_for().bad_xml('trace', str(e))

    await TraceService.update(trace_id, new_trace)
    return Response()


@router.delete('/gpx/{trace_id:int}')
async def gpx_delete(
    trace_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_gpx)],
):
    await TraceService.delete(trace_id)
    return Response()
