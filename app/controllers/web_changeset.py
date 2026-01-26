from asyncio import TaskGroup
from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Form, Query, Response
from psycopg.sql import SQL
from shapely import measurement

from app.config import (
    CHANGESET_COMMENT_BODY_MAX_LENGTH,
    CHANGESET_COMMENTS_PAGE_SIZE,
    CHANGESET_QUERY_WEB_LIMIT,
)
from app.format import FormatRender
from app.format.element_list import FormatElementList
from app.lib.auth_context import web_user
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.lib.rich_text import process_rich_text_plain
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_paginate_table,
    sp_render_response_bytes,
)
from app.lib.translation import t
from app.models.db.changeset_comment import (
    ChangesetComment,
    changeset_comments_resolve_rich_text,
)
from app.models.db.user import User, user_proto
from app.models.proto.changeset_pb2 import (
    ChangesetCommentPage,
    ChangesetCommentResult,
    ChangesetData,
)
from app.models.proto.shared_pb2 import Bounds
from app.models.types import ChangesetId
from app.queries.changeset_bounds_query import ChangesetBoundsQuery
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.changeset_comment_service import ChangesetCommentService
from app.validators.display_name import DisplayNameNormalizing

router = APIRouter(prefix='/api/web/changeset')


@router.post('/{changeset_id:int}/comment')
async def create_comment(
    changeset_id: ChangesetId,
    comment: Annotated[
        str, Form(min_length=1, max_length=CHANGESET_COMMENT_BODY_MAX_LENGTH)
    ],
    _: Annotated[User, web_user()],
):
    await ChangesetCommentService.comment(changeset_id, comment)

    async with TaskGroup() as tg:
        changeset_t = tg.create_task(build_changeset_data(changeset_id))
        comments_t = tg.create_task(build_changeset_comments_page(changeset_id))

    comments_page, state = comments_t.result()
    result = ChangesetCommentResult(
        changeset=changeset_t.result(), comments=comments_page
    )
    return sp_render_response_bytes(result.SerializeToString(), state)


@router.get('/map')
async def get_map(
    bbox: Annotated[str | None, Query()] = None,
    scope: Annotated[
        Literal['nearby', 'friends'] | None, Query()
    ] = None,  # TODO: support scope
    display_name: Annotated[DisplayNameNormalizing | None, Query(min_length=1)] = None,
    date_: Annotated[date | None, Query(alias='date')] = None,
    before: Annotated[ChangesetId | None, Query()] = None,
):
    geometry = parse_bbox(bbox)

    if display_name is not None:
        user = await UserQuery.find_by_display_name(display_name)
        user_ids = [user['id']] if user is not None else []
    else:
        user_ids = None

    if date_ is not None:
        dt = datetime.combine(date_, time(0, 0, 0))
        created_before = dt + timedelta(days=1)
        created_after = dt - timedelta(microseconds=1)
    else:
        created_before = None
        created_after = None

    changesets = await ChangesetQuery.find(
        changeset_id_before=before,
        user_ids=user_ids,
        created_before=created_before,
        created_after=created_after,
        geometry=geometry,
        sort='desc',
        limit=CHANGESET_QUERY_WEB_LIMIT,
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(changesets))
        tg.create_task(ChangesetBoundsQuery.resolve_bounds(changesets))
        tg.create_task(ChangesetCommentQuery.resolve_num_comments(changesets))

    return Response(
        FormatRender.encode_changesets(changesets).SerializeToString(),
        media_type='application/x-protobuf',
    )


@router.post('/{changeset_id:int}/comments')
async def comments_page(
    changeset_id: ChangesetId,
    sp_state: StandardPaginationStateBody = b'',
):
    page, state = await build_changeset_comments_page(changeset_id, sp_state)
    return sp_render_response_bytes(page.SerializeToString(), state)


async def build_changeset_data(changeset_id: ChangesetId):
    changeset = await ChangesetQuery.find_by_id(changeset_id)
    if changeset is None:
        raise_for.changeset_not_found(changeset_id)

    async def elements_task():
        return await FormatElementList.changeset_elements(
            await ElementQuery.find_by_changeset(changeset_id, sort_by='typed_id'),
        )

    async def adjacent_task():
        changeset_user_id = changeset['user_id']
        if changeset_user_id is None:
            return None, None
        return await ChangesetQuery.find_adjacent_ids(
            changeset_id, user_id=changeset_user_id
        )

    async with TaskGroup() as tg:
        items = [changeset]
        tg.create_task(UserQuery.resolve_users(items))
        tg.create_task(ChangesetBoundsQuery.resolve_bounds(items))
        elements_t = tg.create_task(elements_task())
        adjacent_t = tg.create_task(adjacent_task())
        is_subscribed_t = tg.create_task(
            UserSubscriptionQuery.is_subscribed('changeset', changeset_id)
        )

    elements = elements_t.result()
    prev_changeset_id, next_changeset_id = adjacent_t.result()

    tags = changeset['tags']
    comment_text = tags.pop('comment', None) or t('browse.no_comment')
    comment_html = process_rich_text_plain(comment_text)

    bboxes: list[list[float]] = (
        measurement.bounds(bounds.geoms).tolist()  # type: ignore
        if (bounds := changeset.get('bounds')) is not None
        else []
    )

    user = changeset.get('user')
    return ChangesetData(
        id=changeset_id,
        user=user_proto(user),
        created_at=int(changeset['created_at'].timestamp()),
        closed_at=(
            int(changeset['closed_at'].timestamp()) if changeset['closed_at'] else None
        ),
        num_create=changeset['num_create'],
        num_modify=changeset['num_modify'],
        num_delete=changeset['num_delete'],
        comment_rich=comment_html,
        tags=tags,
        bounds=[
            Bounds(min_lon=b[0], min_lat=b[1], max_lon=b[2], max_lat=b[3])
            for b in bboxes
        ],
        nodes=elements['node'],
        ways=elements['way'],
        relations=elements['relation'],
        prev_changeset_id=prev_changeset_id,
        next_changeset_id=next_changeset_id,
        is_subscribed=is_subscribed_t.result(),
    )


async def build_changeset_comments_page(
    changeset_id: ChangesetId, sp_state: bytes = b''
):
    comments, state = await sp_paginate_table(
        ChangesetComment,
        sp_state,
        table='changeset_comment',
        where=SQL('changeset_id = %s'),
        params=(changeset_id,),
        page_size=CHANGESET_COMMENTS_PAGE_SIZE,
        order_dir='desc',
        display_dir='asc',
    )

    async with TaskGroup() as tg:
        tg.create_task(UserQuery.resolve_users(comments))
        tg.create_task(changeset_comments_resolve_rich_text(comments))

    page = ChangesetCommentPage(
        comments=[
            ChangesetCommentPage.Comment(
                user=user_proto(c['user']),  # type: ignore
                created_at=int(c['created_at'].timestamp()),
                body_rich=c['body_rich'],  # type: ignore
            )
            for c in comments
        ]
    )
    return page, state
