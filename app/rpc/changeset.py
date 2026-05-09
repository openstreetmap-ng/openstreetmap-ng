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
from app.lib.standard_pagination import (
    StandardPaginationRequestLike,
    sp_paginate_table,
)
from app.lib.translation import t
from app.models.db.changeset_comment import (
    ChangesetComment,
    changeset_comments_resolve_rich_text,
)
from app.models.db.element import Element
from app.models.db.user import user_proto
from app.models.element import TypedElementId
from app.models.proto.changeset_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.changeset_pb2 import (
    AddCommentRequest,
    AddCommentResponse,
    Data,
    DiffAction,
    GetCommentsRequest,
    GetCommentsResponse,
    GetDiffRequest,
    GetDiffResponse,
    GetMapRequest,
    GetMapResponse,
    GetRequest,
    GetResponse,
    UpdateSubscriptionRequest,
    UpdateSubscriptionResponse,
)
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
from speedup import element_type


class _Service(Service):
    @override
    async def get_map(self, request: GetMapRequest, ctx: RequestContext):
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

        elif scope == GetMapRequest.Scope.nearby:
            current_user = require_web_user()
            home_point = current_user['home_point']
            if home_point is None:
                return GetMapResponse()

            home = set_srid(Point(home_point.x, home_point.y), 4326)
            nearby_area = home.buffer(meters_to_degrees(NEARBY_USERS_RADIUS_METERS), 4)
            geometry = (
                nearby_area if geometry is None else geometry.intersection(nearby_area)
            )
            if geometry.is_empty:
                return GetMapResponse()

        elif scope == GetMapRequest.Scope.friends:
            current_user = require_web_user()
            followee_ids = await UserFollowQuery.get_followee_ids(current_user['id'])
            if not followee_ids:
                return GetMapResponse()

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
                    return GetMapResponse()

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
    async def get(self, request: GetRequest, ctx: RequestContext):
        id = ChangesetId(request.id)
        return GetResponse(changeset=await _build_data(id))

    @override
    async def get_diff(self, request: GetDiffRequest, ctx: RequestContext):
        id = ChangesetId(request.id)
        return await _build_diff(id)

    @override
    async def get_comments(self, request: GetCommentsRequest, ctx: RequestContext):
        id = ChangesetId(request.id)
        if await ChangesetQuery.find_by_id(id) is None:
            raise_for.changeset_not_found(id)

        return await _build_comments(id, request.state)

    @override
    async def add_comment(self, request: AddCommentRequest, ctx: RequestContext):
        require_web_user()

        id = ChangesetId(request.id)
        await ChangesetCommentService.comment(id, request.body)

        async with TaskGroup() as tg:
            changeset_t = tg.create_task(_build_data(id))
            comments_t = tg.create_task(_build_comments(id))

        return AddCommentResponse(
            changeset=changeset_t.result(),
            comments=comments_t.result(),
        )

    @override
    async def update_subscription(
        self, request: UpdateSubscriptionRequest, ctx: RequestContext
    ):
        require_web_user()

        id = ChangesetId(request.id)
        if request.is_subscribed:
            await UserSubscriptionService.subscribe('changeset', id)
        else:
            await UserSubscriptionService.unsubscribe('changeset', id)

        return UpdateSubscriptionResponse()


service = _Service()
asgi_app_cls = ServiceASGIApplication


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

    result = Data(
        id=changeset_id,
        created_at=int(changeset['created_at'].timestamp()),
        num_create=changeset['num_create'],
        num_modify=changeset['num_modify'],
        num_delete=changeset['num_delete'],
        comment_rich=comment_html,
        tags=tags,
        is_subscribed=is_subscribed_t.result(),
    )
    if (user := user_proto(changeset.get('user'))) is not None:
        result.user.CopyFrom(user)
    if changeset['closed_at']:
        result.closed_at = int(changeset['closed_at'].timestamp())
    for b in bboxes:
        bound = result.bounds.add()
        bound.min_lon = b[0]
        bound.min_lat = b[1]
        bound.max_lon = b[2]
        bound.max_lat = b[3]
    result.nodes.extend(elements['node'])
    result.ways.extend(elements['way'])
    result.relations.extend(elements['relation'])
    if prev_changeset_id is not None:
        result.prev_changeset_id = prev_changeset_id
    if next_changeset_id is not None:
        result.next_changeset_id = next_changeset_id
    return result


async def _build_diff(changeset_id: ChangesetId):
    if await ChangesetQuery.find_by_id(changeset_id) is None:
        raise_for.changeset_not_found(changeset_id)

    elements = await ElementQuery.find_by_changeset(changeset_id, sort_by='sequence_id')
    if not elements:
        return GetDiffResponse()

    prev_refs: list[tuple[TypedElementId, int]] = [
        (element['typed_id'], element['version'] - 1)
        for element in elements
        if not element['visible'] and element['version'] > 1
    ]
    prev_elements = await ElementQuery.find_by_versioned_refs(
        prev_refs, limit=len(prev_refs)
    )
    prev_type_id_map = {element['typed_id']: element for element in prev_elements}

    async with TaskGroup() as tg:
        tasks = [
            (
                element,
                tg.create_task(
                    _render_diff_element(
                        prev_type_id_map[element['typed_id']]
                        if not element['visible']
                        and element['typed_id'] in prev_type_id_map
                        else element
                    )
                ),
            )
            for element in elements
        ]

    response = GetDiffResponse()
    for element, task in tasks:
        item = response.elements.add()
        item.action = _changeset_element_action(element)
        item.render.CopyFrom(task.result())
    return response


async def _render_diff_element(element: Element):
    if not element['visible']:
        return FormatRender.encode_elements([], detailed=True)

    type = element_type(element['typed_id'])
    if type == 'node':
        return FormatRender.encode_elements([element], detailed=True)

    if type == 'way':
        members = element['members']
        if not members:
            return FormatRender.encode_elements([], detailed=True)
        nodes = await ElementQuery.find_by_refs(
            members,
            at_sequence_id=element['sequence_id'],
            limit=len(members),
        )
        return FormatRender.encode_elements([element, *nodes], detailed=True)

    return FormatRender.encode_elements([], detailed=True)


def _changeset_element_action(element: Element):
    if not element['visible']:
        return DiffAction.delete
    if element['version'] == 1:
        return DiffAction.create
    return DiffAction.modify


async def _build_comments(
    changeset_id: ChangesetId, sp_state: StandardPaginationRequestLike = b''
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

    page = GetCommentsResponse()
    page.state.CopyFrom(state)
    for c in comments:
        comment = page.comments.add()
        comment.user.CopyFrom(user_proto(c['user']))  # type: ignore
        comment.created_at = int(c['created_at'].timestamp())
        comment.body_rich = c['body_rich']  # type: ignore
    return page
