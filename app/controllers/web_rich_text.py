from typing import Annotated

from fastapi import APIRouter, Form
from starlette.responses import HTMLResponse

from app.lib.auth_context import web_user
from app.lib.rich_text import TextFormat, rich_text
from app.models.db.user import User

router = APIRouter(prefix='/api/web/rich-text')


@router.post('/preview')
async def preview(
    text: Annotated[str, Form()],
    _: Annotated[User, web_user()],
):
    cache_entry = await rich_text(text, None, TextFormat.markdown)
    return HTMLResponse(cache_entry.value)
