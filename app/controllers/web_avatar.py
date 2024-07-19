from typing import Annotated

import magic
from fastapi import APIRouter, Path, Response
from pydantic import PositiveInt

from app.lib.storage.base import StorageKey
from app.queries.avatar_query import AvatarQuery

router = APIRouter(prefix='/api/web/avatar')


@router.get('/gravatar/{user_id:int}')
async def gravatar(
    user_id: Annotated[PositiveInt, Path()],
) -> Response:
    file = await AvatarQuery.get_gravatar(user_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)


@router.get('/custom/{avatar_id}')
async def custom(
    avatar_id: Annotated[StorageKey, Path(min_length=1)],
) -> Response:
    file = await AvatarQuery.get_custom(avatar_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)
