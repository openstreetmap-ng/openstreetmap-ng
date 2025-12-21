from typing import Annotated

from fastapi import APIRouter, Form
from starlette.responses import HTMLResponse

from app.config import (
    CHANGESET_COMMENT_BODY_MAX_LENGTH,
    DIARY_BODY_MAX_LENGTH,
    MESSAGE_BODY_MAX_LENGTH,
    NOTE_COMMENT_BODY_MAX_LENGTH,
    REPORT_COMMENT_BODY_MAX_LENGTH,
    USER_BLOCK_BODY_MAX_LENGTH,
    USER_DESCRIPTION_MAX_LENGTH,
)
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.lib.rich_text import rich_text
from app.models.db.user import User

router = APIRouter(prefix='/api/web/rich-text')

_PREVIEW_MAX_LENGTH = max(
    CHANGESET_COMMENT_BODY_MAX_LENGTH,
    DIARY_BODY_MAX_LENGTH,
    MESSAGE_BODY_MAX_LENGTH,
    NOTE_COMMENT_BODY_MAX_LENGTH,
    REPORT_COMMENT_BODY_MAX_LENGTH,
    USER_BLOCK_BODY_MAX_LENGTH,
    USER_DESCRIPTION_MAX_LENGTH,
)


@router.post('')
async def preview(
    _: Annotated[User, web_user()],
    text: Annotated[str, Form(max_length=_PREVIEW_MAX_LENGTH)] = '',
):
    html = (await rich_text(text, None, 'markdown'))[0]
    if html:
        return HTMLResponse(html)
    return await render_response('rich-text/_empty')
