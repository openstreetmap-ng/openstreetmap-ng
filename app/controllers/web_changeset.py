from collections.abc import Collection
from typing import Annotated, Literal

from fastapi import APIRouter, Form, Query, Response
from pydantic import PositiveInt
from sqlalchemy.orm import joinedload

from app.format import FormatLeaflet
from app.lib.auth_context import web_user
from app.lib.geo_utils import parse_bbox
from app.lib.options_context import options_context
from app.limits import CHANGESET_COMMENT_BODY_MAX_LENGTH, CHANGESET_QUERY_WEB_LIMIT, DISPLAY_NAME_MAX_LENGTH
from app.models.db.changeset import Changeset
from app.models.db.user import User
from app.models.types import DisplayNameType
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_query import UserQuery
from app.services.changeset_comment_service import ChangesetCommentService

router = APIRouter(prefix='/api/web/changeset')


@router.post('/{changeset_id:int}/comment')
async def create_comment(
    changeset_id: PositiveInt,
    comment: Annotated[str, Form(min_length=1, max_length=CHANGESET_COMMENT_BODY_MAX_LENGTH)],
    _: Annotated[User, web_user()],
):
    await ChangesetCommentService.comment(changeset_id, comment)
    return Response()


@router.get('/map')
async def get_map(
    bbox: Annotated[str | None, Query()] = None,
    scope: Annotated[Literal['nearby', 'friends'] | None, Query()] = None,  # TODO: support scope
    display_name: Annotated[DisplayNameType | None, Query(min_length=1, max_length=DISPLAY_NAME_MAX_LENGTH)] = None,
    before: Annotated[PositiveInt | None, Query()] = None,
):
    user_ids: Collection[int] | None = None
    geometry = parse_bbox(bbox) if (bbox is not None) else None
    if display_name is not None:
        user = await UserQuery.find_one_by_display_name(display_name)
        user_ids = (user.id,) if (user is not None) else ()
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
            user_ids=user_ids,
            geometry=geometry,
            sort='desc',
            limit=CHANGESET_QUERY_WEB_LIMIT,
        )
    await ChangesetCommentQuery.resolve_num_comments(changesets)
    return Response(
        FormatLeaflet.encode_changesets(changesets).SerializeToString(),
        media_type='application/x-protobuf',
    )
