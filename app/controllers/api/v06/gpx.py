import logging
from typing import Annotated

import magic
from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import PositiveInt

from app.format06 import Format06
from app.lib.auth_context import api_user
from app.lib.exceptions_context import raise_for
from app.lib.joinedload_context import joinedload_context
from app.lib.xmltodict import XMLToDict
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


@router.post('/gpx/create', response_class=PlainTextResponse)
async def gpx_create(
    _: Annotated[User, api_user(Scope.write_gpx)],
    file: Annotated[UploadFile, File()],
    description: Annotated[Str255, Form()],
    tags: Annotated[str, Form()] = '',
    visibility: Annotated[TraceVisibility | None, Form()] = None,
    public: Annotated[int, Form(deprecated=True)] = 0,
) -> int:
    if visibility is None:
        # backwards compatibility:
        # if public (numeric) is non-zero, set visibility to public
        visibility = TraceVisibility.public if public else TraceVisibility.private

    trace = await TraceService.upload(file, description, tags, visibility)
    return trace.id


@router.get('/gpx/{trace_id}')
@router.get('/gpx/{trace_id}.xml')
@router.get('/gpx/{trace_id}/details')
@router.get('/gpx/{trace_id}/details.xml')
async def gpx_read(
    trace_id: PositiveInt,
) -> dict:
    with joinedload_context(Trace.user):
        trace = await TraceRepository.get_one_by_id(trace_id)
    return Format06.encode_gpx_file(trace)


@router.get('/gpx/{trace_id}/data.xml', response_class=GPXResponse)
@router.get('/gpx/{trace_id}/data.gpx', response_class=GPXResponse)
async def gpx_read_data(
    trace_id: PositiveInt,
) -> dict:
    with joinedload_context(Trace.points, TracePoint.trace):
        trace = await TraceRepository.get_one_by_id(trace_id)
    return Format06.encode_track(trace.points)


@router.get('/gpx/{trace_id}/data')
async def gpx_read_data_raw(
    trace_id: PositiveInt,
) -> Response:
    filename, file = await TraceRepository.get_one_data_by_id(trace_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    logging.debug('Downloading trace file content type is %r', content_type)

    return Response(
        content=file,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        media_type=content_type,
    )


@router.put('/gpx/{trace_id}', response_class=PlainTextResponse)
async def gpx_update(
    request: Request,
    trace_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_gpx)],
) -> None:
    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get('gpx_file', {})

    if not data:
        raise_for().bad_xml('trace', xml, "XML doesn't contain an osm/gpx_file element.")

    try:
        new_trace = Format06.decode_gpx_file(data)
    except Exception as e:
        raise_for().bad_xml('trace', xml, str(e))

    await TraceService.update(trace_id, new_trace)


@router.delete('/gpx/{trace_id}', response_class=PlainTextResponse)
async def gpx_delete(
    trace_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_gpx)],
) -> None:
    await TraceService.delete(trace_id)
