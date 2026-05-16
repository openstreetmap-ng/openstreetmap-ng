from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter

from app.lib.auth.context import web_user
from app.lib.render.proto import render_proto_page
from app.lib.text.translation import t
from app.models.db.user import User
from app.models.proto.follow_pb2 import IndexPage
from app.queries.user_follow_query import UserFollowQuery

router = APIRouter()


@router.get('/follows/followers')
async def followers(user: Annotated[User, web_user()]):
    return await _follows(user, title_prefix=t('follows.followers'))


@router.get('/follows/following')
async def following(user: Annotated[User, web_user()]):
    return await _follows(user, title_prefix=t('follows.following'))


async def _follows(user: User, *, title_prefix: str):
    async with TaskGroup() as tg:
        following_t = tg.create_task(
            UserFollowQuery.count_user_follows(user['id'], followers=False)
        )
        followers_t = tg.create_task(
            UserFollowQuery.count_user_follows(user['id'], followers=True)
        )

    page = IndexPage(
        followers_count=followers_t.result(),
        following_count=following_t.result(),
    )
    return await render_proto_page(page, title_prefix=title_prefix)
