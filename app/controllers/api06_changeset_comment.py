from typing import Annotated

from fastapi import APIRouter, Form
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.format import Format06
from app.lib.auth_context import api_user
from app.lib.options_context import options_context
from app.limits import CHANGESET_COMMENT_BODY_MAX_LENGTH
from app.models.db.changeset import Changeset
from app.models.db.user import User
from app.models.db.user_subscription import UserSubscriptionTarget
from app.models.scope import Scope
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.services.changeset_comment_service import ChangesetCommentService
from app.services.user_subscription_service import UserSubscriptionService

router = APIRouter(prefix='/api/0.6')


@router.post('/changeset/{changeset_id:int}/comment')
async def create_changeset_comment(
    changeset_id: PositiveInt,
    text: Annotated[str, Form(min_length=1, max_length=CHANGESET_COMMENT_BODY_MAX_LENGTH)],
    _: Annotated[User, api_user(Scope.write_api)],
):
    await ChangesetCommentService.comment(changeset_id, text)
    return await _get_response(changeset_id)


@router.delete('/changeset/comment/{comment_id:int}')
async def delete_changeset_comment(
    comment_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api, Scope.role_moderator)],
):
    changeset_id = await ChangesetCommentService.delete_comment_unsafe(comment_id)
    return await _get_response(changeset_id)


@router.post('/changeset/{changeset_id:int}/subscribe')
async def changeset_subscribe(
    changeset_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api)],
):
    await UserSubscriptionService.subscribe(UserSubscriptionTarget.changeset, changeset_id)
    return await _get_response(changeset_id)


@router.post('/changeset/{changeset_id:int}/unsubscribe')
async def changeset_unsubscribe(
    changeset_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api)],
):
    await UserSubscriptionService.unsubscribe(UserSubscriptionTarget.changeset, changeset_id)
    return await _get_response(changeset_id)


async def _get_response(changeset_id: int):
    with options_context(joinedload(Changeset.user).load_only(User.display_name)):
        changeset = await ChangesetQuery.find_by_id(changeset_id)
    if changeset is None:
        raise AssertionError(f'Changeset {changeset_id} must exist in database')
    changesets = (changeset,)
    await ChangesetCommentQuery.resolve_num_comments(changesets)
    return Format06.encode_changesets(changesets)


# TODO: hide/unhide
