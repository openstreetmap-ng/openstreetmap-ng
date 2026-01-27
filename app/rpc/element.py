from asyncio import TaskGroup
from typing import override

from connectrpc.request import RequestContext
from psycopg.sql import SQL, Identifier
from shapely import get_coordinates

from app.config import ELEMENT_HISTORY_PAGE_SIZE
from app.format import FormatRender
from app.format.element_list import FormatElementList
from app.lib.exceptions_context import raise_for
from app.lib.feature_icon import features_icons
from app.lib.feature_name import features_names
from app.lib.rich_text import process_rich_text_plain
from app.lib.standard_pagination import sp_num_pages, sp_paginate_query
from app.lib.translation import t
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import user_proto
from app.models.element import ElementId
from app.models.proto.element_connect import (
    ElementService,
    ElementServiceASGIApplication,
)
from app.models.proto.element_pb2 import (
    ElementData,
    GetElementHistoryRequest,
    GetElementHistoryResponse,
    GetElementRequest,
    GetElementResponse,
    RenderElementsData,
)
from app.models.proto.shared_pb2 import ElementIcon, ElementVersionRef, LonLat
from app.models.proto.shared_pb2 import ElementType as ProtoElementType
from app.models.types import SequenceId
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from speedup import split_typed_element_id, typed_element_id


class _Service(ElementService):
    @override
    async def get_element(self, request: GetElementRequest, ctx: RequestContext):
        ref_kind = request.WhichOneof('ref')
        ref: ElementVersionRef = getattr(request, ref_kind)
        tid = typed_element_id(ProtoElementType.Name(ref.type), ElementId(ref.id))

        at_sequence_id = await ElementQuery.get_current_sequence_id()

        if ref_kind == 'version':
            versioned_tid = (tid, ref.version)
            elements = await ElementQuery.find_by_versioned_refs(
                [versioned_tid], at_sequence_id=at_sequence_id, limit=1
            )
        else:
            elements = await ElementQuery.find_by_refs(
                [tid], at_sequence_id=at_sequence_id, limit=1
            )

        element = next(iter(elements), None)
        if element is None:
            raise_for.element_not_found(tid)

        return GetElementResponse(
            element=await _build_data(
                element,
                at_sequence_id,
                include_parents_entries=ref_kind == 'element' or element['latest'],
            )
        )

    @override
    async def get_element_history(
        self, request: GetElementHistoryRequest, ctx: RequestContext
    ):
        type = ProtoElementType.Name(request.element.type)
        id = ElementId(request.element.id)
        tid = typed_element_id(type, id)

        sp_state = request.state.SerializeToString()
        elements, state = await sp_paginate_query(
            Element,
            sp_state,
            select=SQL('*'),
            from_=Identifier('element'),
            where=SQL('typed_id = %s'),
            params=(tid,),
            cursor_key='sequence_id',
            id_key='version',
            page_size=ELEMENT_HISTORY_PAGE_SIZE,
            cursor_kind='id',
            order_dir='desc',
        )

        if state.snapshot_max_id == 0:
            raise_for.element_not_found(tid)

        at_sequence_id: SequenceId = state.u64.snapshot  # type: ignore

        num_items = state.snapshot_max_id
        state.num_items = num_items
        state.num_pages = sp_num_pages(
            num_items=num_items, page_size=ELEMENT_HISTORY_PAGE_SIZE
        )
        state.max_known_page = state.num_pages

        if not elements:
            return GetElementHistoryResponse(state=state, elements=())

        changeset_ids = list({e['changeset_id'] for e in elements})

        async with TaskGroup() as tg:
            changesets_t = tg.create_task(ChangesetQuery.find_by_ids(changeset_ids))
            previous_t = (
                tg.create_task(
                    ElementQuery.find_by_versioned_refs(
                        [(tid, elements[-1]['version'] - 1)],
                        at_sequence_id=at_sequence_id,
                        limit=1,
                    )
                )
                if request.tags_diff and elements[-1]['version'] > 1
                else None
            )

        changesets = changesets_t.result()
        await UserQuery.resolve_users(changesets)
        changeset_id_map = {c['id']: c for c in changesets}

        async with TaskGroup() as tg:

            async def data_task(element):
                changeset = changeset_id_map.get(element['changeset_id'])
                assert changeset is not None, 'Parent changeset must exist'
                return await _build_data(
                    element,
                    at_sequence_id,
                    changeset=changeset,
                    include_members_entries=False,
                    include_parents_entries=False,
                )

            elements_tasks = [
                tg.create_task(data_task(element)) for element in elements
            ]

        elements_data = [task.result() for task in elements_tasks]

        if request.tags_diff:
            if previous_t is not None:
                previous = previous_t.result()
                previous_tags = (previous[0]['tags'] or {}) if previous else {}
            else:
                previous_tags = None

            for element, element_data in zip(
                reversed(elements),
                reversed(elements_data),
                strict=True,
            ):
                if previous_tags is not None:
                    element_data.tags_old.update(previous_tags)
                previous_tags = element['tags'] or {}

        return GetElementHistoryResponse(state=state, elements=elements_data)


service = _Service()
asgi_app_cls = ElementServiceASGIApplication


async def _build_data(
    element: Element,
    at_sequence_id: SequenceId,
    *,
    changeset: Changeset | None = None,
    include_members_entries: bool = True,
    include_parents_entries: bool = True,
):
    type, id = split_typed_element_id(element['typed_id'])
    version = element['version']

    async with TaskGroup() as tg:
        context_t = tg.create_task(
            _build_context(
                element,
                at_sequence_id,
                include_members_entries=include_members_entries,
                include_parents_entries=include_parents_entries,
            )
        )
        if changeset is None:
            changeset = await ChangesetQuery.find_by_id(element['changeset_id'])
            assert changeset is not None, 'Parent changeset must exist'
            await UserQuery.resolve_users([changeset])

    comment_text = changeset['tags'].get('comment') or t('browse.no_comment')
    comment_html = process_rich_text_plain(comment_text)

    if (point := element['point']) is not None:
        x, y = get_coordinates(point)[0].tolist()
        location = (x, y)
    else:
        location = None

    prev_version = version - 1 if version > 1 else None
    next_version = version + 1 if not element['latest'] else None
    icon = features_icons([element])[0]
    name = features_names([element])[0]

    return ElementData(
        ref=ElementVersionRef(type=type, id=id, version=version),
        visible=element['visible'],
        name=name,
        icon=(
            ElementIcon(icon=icon.filename, title=icon.title)
            if icon is not None
            else None
        ),
        tags=element['tags'] or {},
        context=context_t.result(),
        changeset=ElementData.Changeset(
            id=element['changeset_id'],
            user=user_proto(changeset.get('user')),
            created_at=int(changeset['created_at'].timestamp()),
            comment_rich=comment_html,
        ),
        prev_version=prev_version,
        next_version=next_version,
        location=(
            LonLat(lon=location[0], lat=location[1])  #
            if location is not None
            else None
        ),
    )


async def _build_context(
    element: Element,
    at_sequence_id: SequenceId,
    *,
    include_members_entries: bool,
    include_parents_entries: bool,
):
    if not element['visible']:
        return ElementData.Context(members=(), parents=(), render=RenderElementsData())

    async def members_task():
        members = element['members']
        members_elements = await ElementQuery.find_by_refs(
            members,
            at_sequence_id=at_sequence_id,
            recurse_ways=True,
            sort_dir='asc',
            limit=None,
        )
        full_data = [element, *members_elements]
        element_members = (
            FormatElementList.element_members(
                members, element['members_roles'], members_elements
            )
            if include_members_entries
            else ()
        )
        render_data = FormatRender.encode_elements(full_data, detailed=True)
        return element_members, render_data

    async def parents_task():
        tid = element['typed_id']
        element_parents = await ElementQuery.find_parents_by_refs(
            [tid],
            at_sequence_id=at_sequence_id,
            limit=None,
        )
        return FormatElementList.element_parents(tid, element_parents)

    async with TaskGroup() as tg:
        members_t = tg.create_task(members_task())
        parents = await parents_task() if include_parents_entries else ()

    members, render = members_t.result()
    return ElementData.Context(members=members, parents=parents, render=render)
