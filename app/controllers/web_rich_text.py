from typing import Annotated

from fastapi import APIRouter, Form

from app.lib.auth_context import web_user
from app.lib.rich_text import rich_text
from app.models.db.user import User
from app.models.text_format import TextFormat

router = APIRouter(prefix='/api/web/rich-text')


@router.post('/preview')
async def preview(
    text: Annotated[str, Form()],
    _: Annotated[User, web_user()],
) -> str:
    cache_entry = await rich_text(text, None, TextFormat.markdown)
    return cache_entry.value.decode()
