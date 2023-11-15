from typing import Annotated

from fastapi import APIRouter, Form
from pydantic import PositiveInt

from lib.auth import api_user
from lib.exceptions import raise_for
from lib.format.format06 import Format06
from models.db.changeset import Changeset
from models.db.changeset_comment import ChangesetComment
from models.db.changeset_subscription import ChangesetSubscription
from models.db.user import User
from models.scope import ExtendedScope, Scope
from models.str import NonEmptyStr

router = APIRouter()

# TODO: retry transactions


@router.post('/changeset/{changeset_id}/subscribe')
async def changeset_subscribe(
    changeset_id: PositiveInt,
    user: Annotated[User, api_user(Scope.write_api)],
) -> dict:
    changeset = await Changeset.find_one_by_id(changeset_id)

    if not changeset:
        raise_for().changeset_not_found(changeset_id)

    try:
        await ChangesetSubscription(user_id=user.id, changeset_id=changeset_id).create()
    except Exception:  # TODO: strict exception
        raise_for().changeset_already_subscribed(changeset_id)

    return Format06.encode_changeset(changeset)


@router.post('/changeset/{changeset_id}/unsubscribe')
async def changeset_unsubscribe(
    changeset_id: PositiveInt,
    user: Annotated[User, api_user(Scope.write_api)],
) -> dict:
    changeset = await Changeset.find_one_by_id(changeset_id)

    if not changeset:
        raise_for().changeset_not_found(changeset_id)

    try:
        await ChangesetSubscription.delete_by({'user_id': user.id, 'changeset_id': changeset_id})
    except Exception:  # TODO: strict exception
        raise_for().changeset_not_subscribed(changeset_id)

    return Format06.encode_changeset(changeset)


@router.post('/changeset/{changeset_id}/comment')
async def changeset_comment(
    changeset_id: PositiveInt,
    text: Annotated[NonEmptyStr, Form()],
    user: Annotated[User, api_user(Scope.write_api)],
) -> dict:
    changeset = await Changeset.find_one_by_id(changeset_id)

    if not changeset:
        raise_for().changeset_not_found(changeset_id)
    if not changeset.closed_at:
        raise_for().changeset_not_closed(changeset_id)

    await ChangesetComment(user_id=user.id, changeset_id=changeset_id, body=text).create()

    return Format06.encode_changeset(changeset, add_comments_count=1)


@router.post('/changeset/comment/{comment_id}/hide')
async def changeset_comment_hide(
    comment_id: PositiveInt,
    _: Annotated[User, api_user(Scope.write_api, ExtendedScope.role_moderator)],
) -> dict:
    comment = await ChangesetComment.find_one_by_id(comment_id)
    if not comment:
        raise_for().changeset_comment_not_found(comment_id)

    changeset = await Changeset.find_one_by_id(comment.changeset_id)
    if not changeset:
        raise_for().changeset_not_found(comment.changeset_id)

    await comment.delete()
    return Format06.encode_changeset(changeset, add_comments_count=-1)
