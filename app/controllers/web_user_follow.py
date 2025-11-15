from typing import Annotated

from fastapi import APIRouter, Path, Response
from starlette import status

from app.lib.auth_context import web_user
from app.models.db.user import User
from app.models.types import UserId
from app.services.user_follow_service import UserFollowService

router = APIRouter(prefix='/api/web/user-follow')


@router.post('/{user_id:int}/follow')
async def follow(
    user_id: Annotated[UserId, Path()],
    _: Annotated[User, web_user()],
):
    """Follow a user."""
    await UserFollowService.follow(user_id)
    return Response(None, status.HTTP_204_NO_CONTENT)


@router.post('/{user_id:int}/unfollow')
async def unfollow(
    user_id: Annotated[UserId, Path()],
    _: Annotated[User, web_user()],
):
    """Unfollow a user."""
    await UserFollowService.unfollow(user_id)
    return Response(None, status.HTTP_204_NO_CONTENT)
