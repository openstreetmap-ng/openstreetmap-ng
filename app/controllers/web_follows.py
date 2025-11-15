from typing import Annotated

from fastapi import APIRouter, Path, Query, Response
from pydantic import PositiveInt
from starlette import status
from starlette.responses import HTMLResponse

from app.lib.auth_context import web_user
from app.lib.render_jinja import render_jinja
from app.models.db.user import User
from app.models.types import UserId
from app.queries.user_follow_query import UserFollowQuery
from app.services.user_follow_service import UserFollowService

router = APIRouter(prefix='/api/web/follows')


@router.get('/followers')
async def followers_page(
    user: Annotated[User, web_user()],
    page: Annotated[PositiveInt, Query()],
    num_items: Annotated[PositiveInt, Query()],
):
    """Get a paginated list of followers."""
    follows = await UserFollowQuery.list_user_follows(
        user['id'], followers=True, page=page, num_items=num_items
    )

    return HTMLResponse(render_jinja('follows/_follows-page', {'follows': follows}))


@router.get('/following')
async def following_page(
    user: Annotated[User, web_user()],
    page: Annotated[PositiveInt, Query()],
    num_items: Annotated[PositiveInt, Query()],
):
    """Get a paginated list of following."""
    follows = await UserFollowQuery.list_user_follows(
        user['id'], followers=False, page=page, num_items=num_items
    )

    return HTMLResponse(render_jinja('follows/_follows-page', {'follows': follows}))


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
