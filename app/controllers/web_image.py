from typing import Annotated

import magic
from fastapi import APIRouter, Path, Response
from pydantic import PositiveInt

from app.models.types import StorageKey
from app.queries.image_query import ImageQuery

router = APIRouter(prefix='/api/web')


@router.get('/gravatar/{user_id:int}')
async def gravatar(user_id: PositiveInt) -> Response:
    file = await ImageQuery.get_gravatar(user_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)


@router.get('/avatar/{avatar_id}')
async def avatar(avatar_id: Annotated[StorageKey, Path(min_length=1)]) -> Response:
    file = await ImageQuery.get_avatar(avatar_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)


@router.get('/background/{background_id}')
async def background(background_id: Annotated[StorageKey, Path(min_length=1)]) -> Response:
    file = await ImageQuery.get_background(background_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)
