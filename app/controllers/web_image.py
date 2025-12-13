from typing import Annotated

import magic
from fastapi import APIRouter, Path, Response
from starlette import status

from app.config import (
    GRAVATAR_CACHE_EXPIRE,
    IMAGE_PROXY_CACHE_EXPIRE,
    INITIALS_CACHE_MAX_AGE,
    STATIC_CACHE_MAX_AGE,
    STATIC_CACHE_STALE,
)
from app.lib.avatar import generate_avatar
from app.middlewares.cache_control_middleware import cache_control
from app.models.types import ImageProxyId, NoteId, StorageKey, UserId
from app.queries.image_query import ImageQuery
from app.queries.note_comment_query import NoteCommentQuery
from app.queries.user_query import UserQuery
from app.services.image_proxy_service import ImageProxyService

router = APIRouter(prefix='/api/web/img')


@router.get('/avatar/anonymous_note/{note_id:int}')
@cache_control(STATIC_CACHE_MAX_AGE, STATIC_CACHE_STALE)
async def anonymous_note_avatar(note_id: NoteId) -> Response:
    comments = await NoteCommentQuery.find_comments_page(
        'page', note_id, page=1, num_items=1, skip_header=False
    )
    comment = next(iter(comments), None)
    if (
        comment is None
        or comment['event'] != 'opened'
        or comment['user_id'] is not None
        or comment['user_ip'] is None
    ):
        return Response(None, status.HTTP_404_NOT_FOUND)

    text = f'{comment["created_at"].year}/{comment["user_ip"]}'
    file = generate_avatar('shapes', text)
    content_type = 'image/svg+xml'
    return Response(file, media_type=content_type)


@router.get('/avatar/initials/{user_id:int}')
@cache_control(INITIALS_CACHE_MAX_AGE, STATIC_CACHE_STALE)
async def text_avatar(user_id: UserId) -> Response:
    user = await UserQuery.find_by_id(user_id)
    if user is None:
        return Response(None, status.HTTP_404_NOT_FOUND)

    file = generate_avatar('initials', user['display_name'])
    content_type = 'image/svg+xml'
    return Response(file, media_type=content_type)


@router.get('/avatar/gravatar/{user_id:int}')
@cache_control(GRAVATAR_CACHE_EXPIRE, STATIC_CACHE_STALE)
async def gravatar(user_id: UserId) -> Response:
    file = await ImageQuery.get_gravatar(user_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)


@router.get('/avatar/custom/{avatar_id}')
@cache_control(STATIC_CACHE_MAX_AGE, STATIC_CACHE_STALE)
async def avatar(avatar_id: Annotated[StorageKey, Path(min_length=1)]) -> Response:
    file = await ImageQuery.get_avatar(avatar_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)


@router.get('/background/custom/{background_id}')
@cache_control(STATIC_CACHE_MAX_AGE, STATIC_CACHE_STALE)
async def background(
    background_id: Annotated[StorageKey, Path(min_length=1)],
) -> Response:
    file = await ImageQuery.get_background(background_id)
    content_type = magic.from_buffer(file[:2048], mime=True)
    return Response(file, media_type=content_type)


@router.get('/proxy/{proxy_id:int}')
@cache_control(IMAGE_PROXY_CACHE_EXPIRE, STATIC_CACHE_STALE)
async def proxy(proxy_id: Annotated[ImageProxyId, Path()]) -> Response:
    file, media_type = await ImageProxyService.fetch(proxy_id)
    return Response(file, media_type=media_type)
