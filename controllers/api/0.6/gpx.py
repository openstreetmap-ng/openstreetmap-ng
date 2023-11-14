import logging
from typing import Annotated

import magic
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse
from httpx import Response

from cython_lib.xmltodict import XMLToDict
from lib.auth import Auth, api_user
from lib.exceptions import exceptions
from lib.format.format06 import Format06
from lib.tracks import Tracks
from models.db.base_sequential import SequentialId
from models.db.trace_ import Trace
from models.db.user import User
from models.scope import Scope
from models.str import Str255
from models.trace_visibility import TraceVisibility

router = APIRouter()


@router.post('/gpx/create', response_class=PlainTextResponse)
async def gpx_create(
    file: Annotated[UploadFile, File()],
    description: Annotated[Str255, Form()],
    tags: Annotated[str, Form('')],
    visibility: Annotated[TraceVisibility | None, Form(None)],
    public: Annotated[int, Form(0, deprecated=True)],
    user: Annotated[User, api_user(Scope.write_gpx)],
) -> SequentialId:
    if not visibility:
        visibility = TraceVisibility.public if public else TraceVisibility.private

    trace = await Tracks.process_upload(file, description, tags, visibility)
    return trace.id


@router.get('/gpx/{trace_id}')
@router.get('/gpx/{trace_id}.xml')
@router.get('/gpx/{trace_id}/details')
@router.get('/gpx/{trace_id}/details.xml')
async def gpx_read(trace_id: SequentialId) -> dict:
    trace = await Trace.get_one_by_id(trace_id)

    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not trace.visible_to(*Auth.user_scopes()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return Format06.encode_gpx_file(trace)


@router.put('/gpx/{trace_id}', response_class=PlainTextResponse)
async def gpx_update(
    request: Request, trace_id: SequentialId, user: Annotated[User, api_user(Scope.write_gpx)]
) -> None:
    trace = await Trace.get_one_by_id(trace_id)

    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if trace.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    xml = (await request.body()).decode()
    data: dict = XMLToDict.parse(xml).get('osm', {}).get('gpx_file', {})

    if not data:
        exceptions().raise_for_bad_xml('trace', xml, "XML doesn't contain an osm/gpx_file element.")

    try:
        new_trace = Format06.decode_gpx_file(data)
    except Exception as e:
        exceptions().raise_for_bad_xml('trace', xml, str(e))

    trace.name = new_trace.name
    trace.description = new_trace.description
    trace.visibility = new_trace.visibility
    trace.tags = new_trace.tags
    await trace.update()


@router.delete('/gpx/{trace_id}', response_class=PlainTextResponse)
async def gpx_delete(trace_id: SequentialId, user: Annotated[User, api_user(Scope.write_gpx)]) -> None:
    trace = await Trace.get_one_by_id(trace_id)

    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if trace.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    await trace.delete()


# TODO: handle .xml ?
@router.get('/gpx/{trace_id}/data')
async def gpx_read_data(trace_id: SequentialId) -> Response:
    trace = await Trace.get_one_by_id(trace_id)

    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not trace.visible_to(*Auth.user_scopes()):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    file = await Tracks.get_file(trace.file_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    logging.debug('Downloading trace file content type is %r', content_type)

    return Response(
        status.HTTP_200_OK,
        headers={'Content-Disposition': f'attachment; filename="{trace.name}"'},
        content=file,
        media_type=content_type,
    )
