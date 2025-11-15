from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter

from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.models.db.user import User
from app.queries.user_follow_query import UserFollowQuery

router = APIRouter()


@router.get('/follows')
async def index(user: Annotated[User, web_user()]):
    """Display the user's following and followers lists."""
    user_id = user['id']

    async def following_task():
        return await UserFollowQuery.list_following(user_id, limit=100)

    async def followers_task():
        return await UserFollowQuery.list_followers(user_id, limit=100)

    async with TaskGroup() as tg:
        following_future = tg.create_task(following_task())
        followers_future = tg.create_task(followers_task())

    following = following_future.result()
    followers = followers_future.result()

    # Resolve is_following status for followers list so we can show "Follow back" vs "Unfollow"
    await UserFollowQuery.resolve_is_following(followers)

    return await render_response(
        'follows/index',
        {
            'following': following,
            'followers': followers,
        },
    )
