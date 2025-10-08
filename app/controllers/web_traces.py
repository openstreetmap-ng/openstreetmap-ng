from typing import Annotated

from fastapi import APIRouter, Form, UploadFile

from app.exceptions.api_error import APIError
from app.lib.auth_context import web_user
from app.lib.standard_feedback import StandardFeedback
from app.models.db.trace import (
    TraceVisibility,
    validate_trace_tags,
)
from app.models.db.user import User
from app.models.types import TraceId
from app.services.trace_service import TraceService

router = APIRouter(prefix='/api/web/traces')


@router.post('/upload')
async def upload(
    _: Annotated[User, web_user()],
    file: Annotated[UploadFile, Form()],
    description: Annotated[str, Form()],
    visibility: Annotated[TraceVisibility, Form()],
    tags: Annotated[list[str] | None, Form()] = None,
):
    try:
        trace_id = await TraceService.upload(
            file, description=description, tags=tags, visibility=visibility
        )
    except* APIError as e:
        # convert api errors to standard feedback errors
        detail = next(exc.detail for exc in e.exceptions if isinstance(exc, APIError))
        StandardFeedback.raise_error(None, detail)

    return {'trace_id': trace_id}


@router.post('/{trace_id:int}/update')
async def update(
    _: Annotated[User, web_user()],
    trace_id: TraceId,
    name: Annotated[str, Form()],
    description: Annotated[str, Form()],
    visibility: Annotated[TraceVisibility, Form()],
    tags: Annotated[list[str] | None, Form()] = None,
):
    try:
        await TraceService.update(
            trace_id,
            name=name,
            description=description,
            tags=validate_trace_tags(tags),
            visibility=visibility,
        )
    except* APIError as e:
        # convert api errors to standard feedback errors
        detail = next(exc.detail for exc in e.exceptions if isinstance(exc, APIError))
        StandardFeedback.raise_error(None, detail)

    return {'trace_id': trace_id}


@router.post('/{trace_id:int}/delete')
async def delete(
    user: Annotated[User, web_user()],
    trace_id: TraceId,
):
    try:
        await TraceService.delete(trace_id)
    except* APIError as e:
        # convert api errors to standard feedback errors
        detail = next(exc.detail for exc in e.exceptions if isinstance(exc, APIError))
        StandardFeedback.raise_error(None, detail)

    return {'redirect_url': f'/user/{user["display_name"]}/traces'}
