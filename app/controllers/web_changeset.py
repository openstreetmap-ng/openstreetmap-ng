from asyncio import TaskGroup
from typing import Annotated, Literal

from fastapi import APIRouter, Form, Path, Query, Response
from pydantic import PositiveInt

from app.format import FormatLeaflet
from app.lib.auth_context import web_user
from app.lib.geo_utils import parse_bbox
from app.lib.render_response import render_response
from app.limits import CHANGESET_COMMENT_BODY_MAX_LENGTH, CHANGESET_QUERY_WEB_LIMIT
from app.models.db.changeset import ChangesetId
from app.models.db.changeset_comment import changeset_comments_resolve_rich_text
from app.models.db.user import User
from app.models.types import DisplayName
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.user_query import UserQuery
from app.services.changeset_comment_service import ChangesetCommentService

router = APIRouter(prefix='/api/web/changeset')


@router.post('/{changeset_id:int}/comment')
async def create_comment(
    changeset_id: Annotated[ChangesetId, Path(gt=0)],
    comment: Annotated[str, Form(min_length=1, max_length=CHANGESET_COMMENT_BODY_MAX_LENGTH)],
    _: Annotated[User, web_user()],
):
    await ChangesetCommentService.comment(changeset_id, comment)
    return Response()


@router.get('/map')
async def get_map(
    bbox: Annotated[str | None, Query()] = None,
    scope: Annotated[Literal['nearby', 'friends'] | None, Query()] = None,  # TODO: support scope
    display_name: Annotated[DisplayName | None, Query(min_length=1)] = None,
    before: Annotated[ChangesetId | None, Query(gt=0)] = None,
):
    geometry = parse_bbox(bbox)

    if display_name is not None:
        user = await UserQuery.find_one_by_display_name(display_name)
        user_ids = [user['id']] if user is not None else []
    else:
        user_ids = None

    changesets = await ChangesetQuery.find_many_by_query(
        changeset_id_before=before,
        user_ids=user_ids,
        geometry=geometry,
        sort='desc',
        limit=CHANGESET_QUERY_WEB_LIMIT,
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(changesets))
        tg.create_task(ChangesetCommentQuery.resolve_num_comments(changesets))

    return Response(
        FormatLeaflet.encode_changesets(changesets).SerializeToString(),
        media_type='application/x-protobuf',
    )


@router.get('/{changeset_id:int}/comments')
async def comments_page(
    changeset_id: Annotated[ChangesetId, Path(gt=0)],
    page: Annotated[PositiveInt, Query()],
    num_items: Annotated[PositiveInt, Query()],
):
    comments = await ChangesetCommentQuery.get_comments_page(changeset_id, page=page, num_items=num_items)

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(changeset_comments_resolve_rich_text(comments))

    return await render_response('changesets/comments_page.jinja2', {'comments': comments})
