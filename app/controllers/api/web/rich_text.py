from typing import Annotated

from fastapi import APIRouter, Form

from app.lib_cython.auth import web_user
from app.lib_cython.rich_text import rich_text
from app.models.db.user import User
from app.models.text_format import TextFormat

router = APIRouter(prefix='/rich_text')


@router.post('/preview')
async def preview(
    text: Annotated[str, Form()],
    text_format: Annotated[TextFormat, Form()],
    _: Annotated[User, web_user()],
) -> str:
    cache = await rich_text(text, None, text_format)
    return cache.value
