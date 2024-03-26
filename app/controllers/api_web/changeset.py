from typing import Annotated

from fastapi import APIRouter, Form, Response
from pydantic import PositiveInt

from app.lib.auth_context import web_user
from app.models.db.user import User
from app.services.changeset_comment_service import ChangesetCommentService

router = APIRouter(prefix='/changeset')

# TODO: subscription


@router.post('/{changeset_id:int}/discussion')
async def create_comment(
    changeset_id: PositiveInt,
    comment: Annotated[str, Form(min_length=1)],
    _: Annotated[User, web_user()],
):
    await ChangesetCommentService.comment(changeset_id, comment)
    return Response()
