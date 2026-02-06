from asyncio import TaskGroup
from datetime import date, datetime, time, timedelta
from typing import override

from connectrpc.request import RequestContext
from psycopg.sql import SQL
from shapely import Point, measurement, set_srid

from app.config import (
    CHANGESET_COMMENTS_PAGE_SIZE,
    CHANGESET_QUERY_WEB_LIMIT,
    NEARBY_USERS_RADIUS_METERS,
)
from app.format import FormatRender
from app.format.element_list import FormatElementList
from app.lib.auth_context import require_web_user
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import meters_to_degrees, parse_bbox
from app.lib.rich_text import process_rich_text_plain
from app.lib.standard_feedback import StandardFeedback
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
    GetMapChangesetsRequest,
    GetMapChangesetsResponse,
    SetChangesetSubscriptionRequest,
    SetChangesetSubscriptionResponse,
)
from app.models.proto.shared_pb2 import Bounds
from app.models.types import ChangesetId
from app.queries.changeset_bounds_query import ChangesetBoundsQuery
from app.queries.changeset_comment_query import ChangesetCommentQuery
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_follow_query import UserFollowQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.changeset_comment_service import ChangesetCommentService
from app.services.user_subscription_service import UserSubscriptionService
from app.validators.unicode import normalize_display_name


class _Service(ChangesetService):
    @override
    async def get_map_changesets(
        self, request: GetMapChangesetsRequest, ctx: RequestContext
    ):
        geometry = parse_bbox(request.bbox) if request.HasField('bbox') else None
        scope = request.scope if request.HasField('scope') else None

        if request.HasField('display_name'):
            target_user = await UserQuery.find_by_display_name(
                normalize_display_name(request.display_name)
            )
            user_ids = [target_user['id']] if target_user is not None else []
        else:
            user_ids = None

        if scope is None:
            pass

        elif scope == GetMapChangesetsRequest.Scope.nearby:
            current_user = require_web_user()
            home_point = current_user['home_point']
            if home_point is None:
                return GetMapChangesetsResponse()

            home = set_srid(Point(home_point.x, home_point.y), 4326)
            nearby_area = home.buffer(meters_to_degrees(NEARBY_USERS_RADIUS_METERS), 4)
            geometry = (
                nearby_area if geometry is None else geometry.intersection(nearby_area)
            )
            if geometry.is_empty:
                return GetMapChangesetsResponse()

        elif scope == GetMapChangesetsRequest.Scope.friends:
            current_user = require_web_user()
            followee_ids = await UserFollowQuery.get_followee_ids(current_user['id'])
            if not followee_ids:
                return GetMapChangesetsResponse()

            if user_ids is None:
                user_ids = followee_ids
            else:
                if len(user_ids) <= len(followee_ids):
                    set_ = set(followee_ids)
                    user_ids = [uid for uid in user_ids if uid in set_]
                else:
                    set_ = set(user_ids)
                    user_ids = [uid for uid in followee_ids if uid in set_]

                if not user_ids:
                    return GetMapChangesetsResponse()

        if request.HasField('date'):
            try:
                date_ = date.fromisoformat(request.date)
            except ValueError as exc:
                StandardFeedback.raise_error('date', 'Invalid date format', exc=exc)

            dt = datetime.combine(date_, time(0, 0, 0))
            created_before = dt + timedelta(days=1)
            created_after = dt - timedelta(microseconds=1)
        else:
            created_before = None
            created_after = None

        changesets = await ChangesetQuery.find(
            changeset_id_before=(
                ChangesetId(request.before) if request.HasField('before') else None
            ),
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

        return FormatRender.encode_changesets(changesets)

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
        await ChangesetCommentService.comment(id, request.body)

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
