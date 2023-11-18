from collections.abc import Sequence
from typing import Annotated

import magic
from fastapi import APIRouter, Path, Response
from pydantic import PositiveInt

from lib.exceptions import raise_for
from lib.storage import AVATAR_STORAGE, GRAVATAR_STORAGE
from services.user_service import UserService

router = APIRouter(prefix='/avatar')


@router.get('/gravatar/{user_id}')
async def gravatar(
    user_id: Annotated[PositiveInt, Path()],
) -> Sequence[dict]:
    user = await UserService.find_one_by_id(user_id)
    if not user:
        raise_for().user_not_found(user_id)

    file = await GRAVATAR_STORAGE.load(user.email)
    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)


@router.get('/custom/{avatar_id}')
async def custom(
    avatar_id: Annotated[str, Path(min_length=1)],
) -> Sequence[dict]:
    try:
        file = await AVATAR_STORAGE.load(avatar_id)
    except FileNotFoundError:
        raise_for().avatar_not_found(avatar_id)

    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)
