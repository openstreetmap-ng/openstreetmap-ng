from typing import Annotated

from fastapi import APIRouter, Form, UploadFile

from app.exceptions.api_error import APIError
from app.lib.auth_context import web_user
from app.lib.message_collector import MessageCollector
from app.models.db.user import User
from app.models.str import Str255
from app.models.trace_visibility import TraceVisibility
from app.services.trace_service import TraceService

router = APIRouter(prefix='/traces')


@router.post('/upload')
async def settings_avatar(
    _: Annotated[User, web_user()],
    file: Annotated[UploadFile, Form()],
    description: Annotated[Str255, Form()],
    visibility: Annotated[TraceVisibility, Form()],
    tags: Annotated[str, Form()] = '',
):
    try:
        trace = await TraceService.upload(file, description, tags, visibility)
    except APIError as e:
        # convert api errors to standard form responses
        collector = MessageCollector()
        collector.raise_error(None, e.detail)
    return {'trace_id': trace.id}
