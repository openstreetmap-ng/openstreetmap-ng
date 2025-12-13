from typing import Annotated

from fastapi import APIRouter, Path, Query, Response
from pydantic import NonNegativeInt, PositiveInt
from starlette import status

from app.config import FOLLOWS_LIST_PAGE_SIZE
from app.lib.auth_context import web_user
from app.lib.render_response import render_response
from app.lib.standard_pagination import sp_apply_headers, sp_resolve_page
from app.models.db.user import User
from app.models.types import UserId
from app.queries.user_follow_query import UserFollowQuery
from app.services.user_follow_service import UserFollowService

router = APIRouter(prefix='/api/web/follows')


@router.get('/followers')
async def followers_page(
    user: Annotated[User, web_user()],
    page: Annotated[NonNegativeInt, Query()],
    num_items: Annotated[int | None, Query()] = None,
):
    """Get a paginated list of followers."""
    sp_request_headers = num_items is None
    if sp_request_headers:
        num_items = await UserFollowQuery.count_user_follows(user['id'], followers=True)

    assert num_items is not None
    page = sp_resolve_page(
        page=page, num_items=num_items, page_size=FOLLOWS_LIST_PAGE_SIZE
    )

    follows = await UserFollowQuery.list_user_follows(
        user['id'], followers=True, page=page, num_items=num_items
    )

    response = await render_response(
        'follows/_follows-page',
        {'follows': follows, 'followers': True},
    )
    if sp_request_headers:
        sp_apply_headers(
            response, num_items=num_items, page_size=FOLLOWS_LIST_PAGE_SIZE
        )
    return response


@router.get('/following')
async def following_page(
    user: Annotated[User, web_user()],
    page: Annotated[NonNegativeInt, Query()],
    num_items: Annotated[int | None, Query()] = None,
):
    """Get a paginated list of following."""
    sp_request_headers = num_items is None
    if sp_request_headers:
        num_items = await UserFollowQuery.count_user_follows(
            user['id'], followers=False
        )

    assert num_items is not None
    page = sp_resolve_page(
        page=page, num_items=num_items, page_size=FOLLOWS_LIST_PAGE_SIZE
    )

    follows = await UserFollowQuery.list_user_follows(
        user['id'], followers=False, page=page, num_items=num_items
    )

    response = await render_response(
        'follows/_follows-page',
        {'follows': follows, 'followers': False},
    )
    if sp_request_headers:
        sp_apply_headers(
            response, num_items=num_items, page_size=FOLLOWS_LIST_PAGE_SIZE
        )
    return response


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
