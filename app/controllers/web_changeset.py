from typing import Annotated

from fastapi import APIRouter, Form, Query, Response
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.format import FormatLeaflet
from app.lib.auth_context import web_user
from app.lib.geo_utils import parse_bbox
from app.lib.options_context import options_context
from app.limits import CHANGESET_COMMENT_BODY_MAX_LENGTH, CHANGESET_QUERY_WEB_LIMIT
from app.models.db.changeset import Changeset
from app.models.db.user import User
from app.models.db.user_subscription import UserSubscriptionTarget
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.services.changeset_comment_service import ChangesetCommentService
from app.services.user_subscription_service import UserSubscriptionService

router = APIRouter(prefix='/api/web/changeset')


@router.post('/{changeset_id:int}/comment')
async def create_comment(
    changeset_id: PositiveInt,
    comment: Annotated[str, Form(min_length=1, max_length=CHANGESET_COMMENT_BODY_MAX_LENGTH)],
    _: Annotated[User, web_user()],
):
    await ChangesetCommentService.comment(changeset_id, comment)
    return Response()


@router.post('/{changeset_id:int}/subscribe')
async def subscribe(
    changeset_id: PositiveInt,
    _: Annotated[User, web_user()],
):
    await UserSubscriptionService.subscribe(UserSubscriptionTarget.changeset, changeset_id)
    return Response()


@router.post('/{changeset_id:int}/unsubscribe')
async def unsubscribe(
    changeset_id: PositiveInt,
    _: Annotated[User, web_user()],
):
    await UserSubscriptionService.unsubscribe(UserSubscriptionTarget.changeset, changeset_id)
    return Response()


@router.get('/map')
async def get_map(
    bbox: Annotated[str, Query()],
    before: Annotated[PositiveInt | None, Query()] = None,
):
    geometry = parse_bbox(bbox)
    with options_context(
        joinedload(Changeset.user).load_only(
            User.id,
            User.display_name,
            User.avatar_type,
            User.avatar_id,
        )
    ):
        changesets = await ChangesetQuery.find_many_by_query(
            changeset_id_before=before,
            geometry=geometry,
            sort='desc',
            limit=CHANGESET_QUERY_WEB_LIMIT,
        )
    await ChangesetCommentQuery.resolve_num_comments(changesets)
    return Response(
        FormatLeaflet.encode_changesets(changesets).SerializeToString(),
        media_type='application/x-protobuf',
    )
