from typing import Annotated

from fastapi import APIRouter, Form

from src.lib.auth import web_user
from src.lib.rich_text import RichText
from src.models.db.user import User
from src.models.text_format import TextFormat

router = APIRouter(prefix='/rich_text')


@router.post('/preview')
async def preview(
    text: Annotated[str, Form()],
    text_format: Annotated[TextFormat, Form()],
    _: Annotated[User, web_user()],
) -> str:
    cache = await RichText.get_cache(text, None, text_format)
    return cache.value
