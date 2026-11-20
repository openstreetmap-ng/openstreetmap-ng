from asyncio import TaskGroup
from datetime import date, datetime, time, timedelta
from typing import override

from connectrpc.request import RequestContext
from shapely import Point, measurement, set_srid

from app.config import (
    CHANGESET_COMMENTS_PAGE_SIZE,
    CHANGESET_QUERY_WEB_LIMIT,
    NEARBY_USERS_RADIUS_METERS,
)
from app.exceptions.context import raise_for
from app.format import FormatRender
from app.format.element_list import FormatElementList
from app.lib.auth.context import require_web_user
from app.lib.geo.distance import meters_to_degrees
from app.lib.geo.parse import parse_bbox
from app.lib.render.rich_text import process_rich_text_plain
from app.lib.standard.feedback import StandardFeedback
from app.lib.standard.pagination import (
    StandardPaginationRequestLike,
    sp_paginate_table,
)
from app.lib.text.translation import t
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
    GetCommentsRequest,
    GetCommentsResponse,
    GetDiffRequest,
    GetDiffResponse,
    GetMapRequest,
    GetMapResponse,
    GetRequest,
    GetResponse,
)
from app.models.proto.element_pb2 import RenderData
from app.models.types import ChangesetId, SequenceId
from app.queries.changeset_query import (
    ChangesetBoundsQuery,
    ChangesetCommentQuery,
    ChangesetQuery,
)
from app.queries.element_query import ElementQuery
from app.queries.user_follow_query import UserFollowQuery
from app.queries.user_query import UserQuery
from app.queries.user_subscription_query import UserSubscriptionQuery
from app.services.changeset_service import ChangesetCommentService
from app.validators.unicode import normalize_display_name
from speedup import element_type

_CHANGESET_DIFF_ELEMENTS_LIMIT = 120
_CHANGESET_DIFF_CONTEXT_LIMIT = 50_000


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
        if await ChangesetQuery.find_by_id(id) is None:
            raise_for.changeset_not_found(id)
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
    """Compare this changeset's first/last versions, not interleaved edits."""
    refs = await ElementQuery.find_changeset_diff_refs(
        changeset_id, limit=_CHANGESET_DIFF_ELEMENTS_LIMIT
    )
    if not refs:
        return GetDiffResponse(before=RenderData(), after=RenderData())

    num_elements = refs[0][-1]
    before_refs = [
        (typed_id, first_version - 1)
        for typed_id, first_version, *_ in refs
        if first_version > 1
    ]
    after_refs = [(typed_id, last_version) for typed_id, _, last_version, *_ in refs]
    before_cutoffs = {
        typed_id: SequenceId(first_sequence_id - 1)
        for typed_id, _, _, first_sequence_id, _, _ in refs
    }
    after_cutoffs = {
        typed_id: last_sequence_id for typed_id, _, _, _, last_sequence_id, _ in refs
    }

    async with TaskGroup() as tg:
        before_roots_t = tg.create_task(
            ElementQuery.find_by_versioned_refs(before_refs)
        )
        after_roots_t = tg.create_task(ElementQuery.find_by_versioned_refs(after_refs))

    # Resolve each root's context at its own edit boundary. A shared changeset
    # cutoff would include unrelated edits or miss members created mid-changeset.
    # Directly changed roots override context to retain this changeset's net edit.
    async with TaskGroup() as tg:
        before_t = tg.create_task(
            _build_diff_render(before_roots_t.result(), before_cutoffs)
        )
        after_t = tg.create_task(
            _build_diff_render(after_roots_t.result(), after_cutoffs)
        )

    before, before_context_truncated = before_t.result()
    after, after_context_truncated = after_t.result()
    return GetDiffResponse(
        before=before,
        after=after,
        num_elements=len(refs),
        num_truncated=num_elements - len(refs),
        context_truncated=before_context_truncated or after_context_truncated,
    )


async def _build_diff_render(
    roots: list[Element], cutoffs: dict[TypedElementId, SequenceId]
) -> tuple[RenderData, bool]:
    """Render independently timed roots using at most two batched context reads."""
    roots.sort(key=lambda element: element['typed_id'])
    root_map = {root['typed_id']: root for root in roots}
    context_refs: dict[tuple[TypedElementId, SequenceId], None] = {}
    context_truncated = False
    # Insertion order is stable by root ID and member order. Cap the collection
    # itself; relation member lists must not create an unbounded temporary set.
    for root in roots:
        if not root['visible']:
            continue
        cutoff = cutoffs[root['typed_id']]
        for member in root['members'] or ():
            # Direct ways already render at their own boundary. Re-expanding one
            # through a relation would mix its version with the relation's nodes.
            if member in cutoffs and element_type(member) == 'way':
                continue
            context_refs[member, cutoff] = None
            if len(context_refs) > _CHANGESET_DIFF_CONTEXT_LIMIT:
                context_refs.popitem()
                context_truncated = True
                break
        if context_truncated:
            break

    direct_refs = list(context_refs)
    members = await ElementQuery.find_by_snapshot_refs([
        ref for ref in direct_refs if ref[0] not in cutoffs
    ])
    snapshots = {(element['typed_id'], cutoff): element for cutoff, element in members}

    node_refs: list[tuple[TypedElementId, SequenceId]] = []
    for typed_id, cutoff in direct_refs:
        member = (
            root_map.get(typed_id)
            if typed_id in cutoffs
            else snapshots.get((typed_id, cutoff))
        )
        if member is None or element_type(typed_id) != 'way':
            continue
        for node_id in member['members'] or ():
            ref = (node_id, cutoff)
            if ref in context_refs:
                continue
            if len(context_refs) >= _CHANGESET_DIFF_CONTEXT_LIMIT:
                context_truncated = True
                break
            context_refs[ref] = None
            node_refs.append(ref)
        if context_truncated and len(context_refs) >= _CHANGESET_DIFF_CONTEXT_LIMIT:
            break

    snapshots.update(
        ((element['typed_id'], cutoff), element)
        for cutoff, element in await ElementQuery.find_by_snapshot_refs([
            ref for ref in node_refs if ref[0] not in cutoffs
        ])
    )

    render = RenderData()
    rendered_nodes: set[tuple[int, float, float]] = set()
    rendered_ways: set[tuple[int, str]] = set()
    for root in roots:
        if not root['visible']:
            continue
        cutoff = cutoffs[root['typed_id']]
        element_map = {root['typed_id']: root}
        for typed_id in root['members'] or ():
            ref = (typed_id, cutoff)
            if ref not in context_refs:
                continue
            member = (
                root_map.get(typed_id) if typed_id in cutoffs else snapshots.get(ref)
            )
            if member is None:
                continue
            element_map[typed_id] = member
            if element_type(typed_id) != 'way':
                continue
            for node_id in member['members'] or ():
                node_ref = (node_id, cutoff)
                if node_ref not in context_refs:
                    continue
                node = (
                    root_map.get(node_id)
                    if node_id in cutoffs
                    else snapshots.get(node_ref)
                )
                if node is not None:
                    element_map[node_id] = node

        # Render per root so identical member IDs at different historical cutoffs
        # do not overwrite each other. Standalone changed nodes remain visible.
        part = FormatRender.encode_elements(
            list(element_map.values()), detailed=True, areas=False
        )
        for node in part.nodes:
            key = (node.id, node.location.lon, node.location.lat)
            if key not in rendered_nodes:
                rendered_nodes.add(key)
                render.nodes.add().CopyFrom(node)
        for way in part.ways:
            key = (way.id, way.line)
            if key not in rendered_ways:
                rendered_ways.add(key)
                render.ways.add().CopyFrom(way)

    return render, context_truncated


async def _build_comments(
    changeset_id: ChangesetId, sp_state: StandardPaginationRequestLike = b''
):
    comments, state = await sp_paginate_table(
        ChangesetComment,
        sp_state,
        table='changeset_comment',
        where=t'changeset_id = {changeset_id}',
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
