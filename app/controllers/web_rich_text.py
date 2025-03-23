from typing import Annotated

from fastapi import APIRouter, Form
from starlette.responses import HTMLResponse

from app.lib.auth_context import web_user
from app.lib.render_jinja import render_jinja
from app.lib.rich_text import rich_text
from app.limits import (
    CHANGESET_COMMENT_BODY_MAX_LENGTH,
    DIARY_BODY_MAX_LENGTH,
    ISSUE_COMMENT_BODY_MAX_LENGTH,
    MESSAGE_BODY_MAX_LENGTH,
    NOTE_COMMENT_BODY_MAX_LENGTH,
    REPORT_BODY_MAX_LENGTH,
    USER_BLOCK_BODY_MAX_LENGTH,
    USER_DESCRIPTION_MAX_LENGTH,
)
from app.models.db.user import User

router = APIRouter(prefix='/api/web/rich-text')

_PREVIEW_MAX_LENGTH = max(
    CHANGESET_COMMENT_BODY_MAX_LENGTH,
    DIARY_BODY_MAX_LENGTH,
    ISSUE_COMMENT_BODY_MAX_LENGTH,
    MESSAGE_BODY_MAX_LENGTH,
    NOTE_COMMENT_BODY_MAX_LENGTH,
    REPORT_BODY_MAX_LENGTH,
    USER_BLOCK_BODY_MAX_LENGTH,
    USER_DESCRIPTION_MAX_LENGTH,
)


@router.post('')
async def preview(
    text: Annotated[str, Form(max_length=_PREVIEW_MAX_LENGTH)],
    _: Annotated[User, web_user()],
):
    html = (await rich_text(text, None, 'markdown'))[0]
    if not html:
        html = render_jinja('rich_text/_empty_preview.jinja2')
    return HTMLResponse(html)
