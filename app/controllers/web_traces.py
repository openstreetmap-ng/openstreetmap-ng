from typing import Annotated

from fastapi import APIRouter, Form, UploadFile
from pydantic import PositiveInt

from app.exceptions.api_error import APIError
from app.lib.auth_context import web_user
from app.lib.standard_feedback import StandardFeedback
from app.models.db.trace_ import TraceVisibility
from app.models.db.user import User
from app.models.types import Str255
from app.services.trace_service import TraceService

router = APIRouter(prefix='/api/web/traces')


@router.post('/upload')
async def upload(
    _: Annotated[User, web_user()],
    file: Annotated[UploadFile, Form()],
    description: Annotated[Str255, Form()],
    visibility: Annotated[TraceVisibility, Form()],
    tags: Annotated[str, Form()] = '',
):
    try:
        trace = await TraceService.upload(file, description=description, tags=tags, visibility=visibility)
    except* APIError as e:
        # convert api errors to standard form responses
        detail = next(exc.detail for exc in e.exceptions if isinstance(exc, APIError))
        StandardFeedback.raise_error(None, detail)
    return {'trace_id': trace.id}


@router.post('/{trace_id:int}/update')
async def update(
    _: Annotated[User, web_user()],
    trace_id: PositiveInt,
    name: Annotated[Str255, Form()],
    description: Annotated[Str255, Form()],
    visibility: Annotated[TraceVisibility, Form()],
    tags: Annotated[str, Form()] = '',
):
    try:
        await TraceService.update(
            trace_id,
            name=name,
            description=description,
            tag_string=tags,
            visibility=visibility,
        )
    except* APIError as e:
        # convert api errors to standard form responses
        detail = next(exc.detail for exc in e.exceptions if isinstance(exc, APIError))
        StandardFeedback.raise_error(None, detail)
    return {'trace_id': trace_id}


@router.post('/{trace_id:int}/delete')
async def delete(
    user: Annotated[User, web_user()],
    trace_id: PositiveInt,
):
    try:
        await TraceService.delete(trace_id)
    except* APIError as e:
        # convert api errors to standard form responses
        detail = next(exc.detail for exc in e.exceptions if isinstance(exc, APIError))
        StandardFeedback.raise_error(None, detail)
    return {'redirect_url': f'/user/{user.display_name}/traces'}
