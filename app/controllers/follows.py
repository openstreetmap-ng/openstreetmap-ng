from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter

from app.config import FOLLOWS_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.models.types import UserId
from app.queries.user_follow_query import UserFollowQuery

router = APIRouter()


async def _get_follows_page(user_id: UserId, *, followers: bool):
    """Helper to render follows page for both followers and following."""
    async with TaskGroup() as tg:
        following_count_t = tg.create_task(
            UserFollowQuery.count_user_follows(user_id, followers=False)
        )
        followers_count_t = tg.create_task(
            UserFollowQuery.count_user_follows(user_id, followers=True)
        )

    following_count = following_count_t.result()
    followers_count = followers_count_t.result()

    return await render_response(
        'follows/index',
        {
            'active_tab': 'followers' if followers else 'following',
            'following_count': following_count,
            'followers_count': followers_count,
            'FOLLOWS_LIST_PAGE_SIZE': FOLLOWS_LIST_PAGE_SIZE,
        },
    )


@router.get('/follows/followers')
async def followers(user: Annotated[User, web_user()]):
    """Display the user's followers list."""
    return await _get_follows_page(user['id'], followers=True)


@router.get('/follows/following')
async def following(user: Annotated[User, web_user()]):
    """Display the user's following list."""
    return await _get_follows_page(user['id'], followers=False)
