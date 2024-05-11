from typing import Annotated

from fastapi import APIRouter, Form, Response
from pydantic import PositiveInt

from app.lib.auth_context import web_user
from app.models.db.user import User
from app.services.changeset_comment_service import ChangesetCommentService
from app.services.changeset_subscription_service import ChangesetSubscriptionService

router = APIRouter(prefix='/api/web/changeset')


@router.post('/{changeset_id:int}/comment')
async def create_comment(
    changeset_id: PositiveInt,
    comment: Annotated[str, Form(min_length=1)],
    _: Annotated[User, web_user()],
):
    await ChangesetCommentService.comment(changeset_id, comment)
    return Response()


@router.post('/{changeset_id:int}/subscribe')
async def subscribe(
    changeset_id: PositiveInt,
    _: Annotated[User, web_user()],
):
    await ChangesetSubscriptionService.subscribe(changeset_id)
    return Response()


@router.post('/{changeset_id:int}/unsubscribe')
async def unsubscribe(
    changeset_id: PositiveInt,
    _: Annotated[User, web_user()],
):
    await ChangesetSubscriptionService.unsubscribe(changeset_id)
    return Response()
