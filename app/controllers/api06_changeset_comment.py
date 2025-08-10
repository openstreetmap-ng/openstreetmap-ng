from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Form

from app.config import CHANGESET_COMMENT_BODY_MAX_LENGTH
from app.format import Format06
from app.lib.auth_context import api_user
from app.models.db.user import User
from app.models.types import ChangesetCommentId, ChangesetId
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_query import UserQuery
from app.services.changeset_comment_service import ChangesetCommentService
from app.services.user_subscription_service import UserSubscriptionService

router = APIRouter(prefix='/api/0.6')


@router.post('/changeset/{changeset_id:int}/comment')
async def create_changeset_comment(
    changeset_id: ChangesetId,
    text: Annotated[
        str, Form(min_length=1, max_length=CHANGESET_COMMENT_BODY_MAX_LENGTH)
    ],
    _: Annotated[User, api_user('write_api')],
):
    await ChangesetCommentService.comment(changeset_id, text)
    return await _get_response(changeset_id)


@router.delete('/changeset/comment/{comment_id:int}')
async def delete_changeset_comment(
    comment_id: ChangesetCommentId,
    _: Annotated[User, api_user('write_api', 'role_moderator')],
):
    changeset_id = await ChangesetCommentService.delete_comment_unsafe(comment_id)
    return await _get_response(changeset_id)


@router.post('/changeset/{changeset_id:int}/subscribe')
async def changeset_subscribe(
    changeset_id: ChangesetId,
    _: Annotated[User, api_user('write_api')],
):
    await UserSubscriptionService.subscribe('changeset', changeset_id)
    return await _get_response(changeset_id)


@router.post('/changeset/{changeset_id:int}/unsubscribe')
async def changeset_unsubscribe(
    changeset_id: ChangesetId,
    _: Annotated[User, api_user('write_api')],
):
    await UserSubscriptionService.unsubscribe('changeset', changeset_id)
    return await _get_response(changeset_id)


async def _get_response(changeset_id: ChangesetId):
    changeset = await ChangesetQuery.find_one_by_id(changeset_id)
    assert changeset is not None
    changesets = [changeset]

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(changesets))
        tg.create_task(ChangesetCommentQuery.resolve_num_comments(changesets))

    return Format06.encode_changesets(changesets)


# TODO: hide/unhide
