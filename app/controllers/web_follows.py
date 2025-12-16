from typing import Annotated

from fastapi import APIRouter, Path, Response
from psycopg.sql import SQL, Identifier
from pydantic import PositiveInt
from starlette import status

from app.config import FOLLOWS_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_paginate_query,
    sp_render_response,
)
from app.models.db.user import User
from app.models.db.user_follow import UserFollow
from app.models.types import UserId
from app.services.user_follow_service import UserFollowService

router = APIRouter(prefix='/api/web/follows')


async def _follows_page(
    *,
    user: User,
    followers: bool,
    sp_state: bytes,
):
    join_column = Identifier('follower_id' if followers else 'followee_id')
    where_column = Identifier('followee_id' if followers else 'follower_id')

    follows, state = await sp_paginate_query(
        UserFollow,
        sp_state,
        select=SQL("""
            u.id,
            u.display_name,
            u.avatar_type,
            u.avatar_id,
            uf.created_at,
            EXISTS (
                SELECT 1 FROM user_follow
                WHERE follower_id = uf.{}
                  AND followee_id = u.id
            ) AS is_following
        """).format(where_column),
        from_=SQL("""
            user_follow uf
            JOIN "user" u ON u.id = uf.{}
        """).format(join_column),
        where=SQL('uf.{} = %s').format(where_column),
        params=(user['id'],),
        cursor_sql=Identifier('uf', 'created_at'),
        id_sql=Identifier('u', 'id'),
        cursor_key='created_at',
        id_key='id',
        page_size=FOLLOWS_LIST_PAGE_SIZE,
        cursor_kind='datetime',
        order_dir='desc',
    )

    return await sp_render_response(
        'follows/_follows-page',
        {'follows': follows, 'followers': followers},
        state,
    )


@router.post('/followers')
async def followers_page(
    user: Annotated[User, web_user()],
    sp_state: StandardPaginationStateBody = b'',
):
    """Get a paginated list of followers."""
    return await _follows_page(user=user, followers=True, sp_state=sp_state)


@router.post('/following')
async def following_page(
    user: Annotated[User, web_user()],
    sp_state: StandardPaginationStateBody = b'',
):
    """Get a paginated list of following."""
    return await _follows_page(user=user, followers=False, sp_state=sp_state)


@router.post('/{user_id:int}/follow')
async def follow(
    user_id: Annotated[UserId, PositiveInt, Path()],
    _: Annotated[User, web_user()],
):
    """Follow a user."""
    await UserFollowService.follow(user_id)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/{user_id:int}/unfollow')
async def unfollow(
    user_id: Annotated[UserId, PositiveInt, Path()],
    _: Annotated[User, web_user()],
):
    """Unfollow a user."""
    await UserFollowService.unfollow(user_id)
    return Response(None, status.HTTP_204_NO_CONTENT)
