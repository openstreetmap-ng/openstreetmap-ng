from asyncio import TaskGroup
from typing import override

from connectrpc.request import RequestContext
from psycopg.sql import SQL
from shapely import measurement

from app.config import (
    CHANGESET_COMMENTS_PAGE_SIZE,
)
from app.format.element_list import FormatElementList
from app.lib.auth_context import require_web_user
from app.lib.exceptions_context import raise_for
from app.lib.rich_text import process_rich_text_plain
from app.lib.standard_pagination import sp_paginate_table
from app.lib.translation import t
from app.models.db.changeset_comment import (
    ChangesetComment,
    changeset_comments_resolve_rich_text,
)
from app.models.db.user import user_proto
from app.models.proto.changeset_connect import (
    ChangesetService,
    ChangesetServiceASGIApplication,
)
from app.models.proto.changeset_pb2 import (
    AddChangesetCommentRequest,
    AddChangesetCommentResponse,
    ChangesetData,
    GetChangesetCommentsRequest,
    GetChangesetCommentsResponse,
    GetChangesetRequest,
    GetChangesetResponse,
    SetChangesetSubscriptionRequest,
    SetChangesetSubscriptionResponse,
)
from app.models.proto.shared_pb2 import Bounds
from app.models.types import ChangesetId
from app.queries.changeset_bounds_query import ChangesetBoundsQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.changeset_comment_service import ChangesetCommentService
from app.services.user_subscription_service import UserSubscriptionService


class _Service(ChangesetService):
    @override
    async def get_changeset(self, request: GetChangesetRequest, ctx: RequestContext):
        id = ChangesetId(request.id)
        return GetChangesetResponse(changeset=await _build_data(id))

    @override
    async def get_changeset_comments(
        self, request: GetChangesetCommentsRequest, ctx: RequestContext
    ):
        id = ChangesetId(request.id)
        if await ChangesetQuery.find_by_id(id) is None:
            raise_for.changeset_not_found(id)

        sp_state = request.state.SerializeToString()
        return await _build_comments(id, sp_state)

    @override
    async def add_changeset_comment(
        self, request: AddChangesetCommentRequest, ctx: RequestContext
    ):
        require_web_user()

        id = ChangesetId(request.id)
        await ChangesetCommentService.comment(id, request.comment)

        async with TaskGroup() as tg:
            changeset_t = tg.create_task(_build_data(id))
            comments_t = tg.create_task(_build_comments(id))

        return AddChangesetCommentResponse(
            changeset=changeset_t.result(),
            comments=comments_t.result(),
        )

    @override
    async def set_changeset_subscription(
        self, request: SetChangesetSubscriptionRequest, ctx: RequestContext
    ):
        require_web_user()

        id = ChangesetId(request.id)
        if request.is_subscribed:
            await UserSubscriptionService.subscribe('changeset', id)
        else:
            await UserSubscriptionService.unsubscribe('changeset', id)

        return SetChangesetSubscriptionResponse(is_subscribed=request.is_subscribed)


service = _Service()
asgi_app_cls = ChangesetServiceASGIApplication


async def _build_data(changeset_id: ChangesetId):
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


async def _build_comments(changeset_id: ChangesetId, sp_state: bytes = b''):
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

    page = GetChangesetCommentsResponse(
        state=state,
        comments=[
            GetChangesetCommentsResponse.Comment(
                user=user_proto(c['user']),  # type: ignore
                created_at=int(c['created_at'].timestamp()),
                body_rich=c['body_rich'],  # type: ignore
            )
            for c in comments
        ],
    )
    return page
