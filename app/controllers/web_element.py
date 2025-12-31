from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Query, Response
from psycopg.sql import SQL, Identifier
from shapely import get_coordinates

from app.config import ELEMENT_HISTORY_PAGE_SIZE
from app.format import FormatRender
from app.format.element_list import FormatElementList
from app.lib.exceptions_context import raise_for
from app.lib.feature_icon import features_icons
from app.lib.feature_name import features_names
from app.lib.rich_text import process_rich_text_plain
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_num_pages,
    sp_paginate_query,
    sp_render_response_bytes,
)
from app.lib.translation import t
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import user_avatar_url
from app.models.element import ElementId, ElementType
from app.models.proto.shared_pb2 import (
    ElementData,
    ElementHistoryPage,
    ElementIcon,
    PartialElementParams,
    RenderElementsData,
)
from app.models.types import SequenceId
from app.queries.changeset_query import ChangesetQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery
from speedup import element_type, split_typed_element_id, typed_element_id

router = APIRouter(prefix='/api/web/element')


@router.get('/{type:element_type}/{id:int}')
async def get_element(type: ElementType, id: ElementId):
    typed_id = typed_element_id(type, id)
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    elements = await ElementQuery.find_by_refs(
        [typed_id], at_sequence_id=at_sequence_id, limit=1
    )
    element = next(iter(elements), None)
    if element is None:
        raise_for.element_not_found(typed_id)

    data = await _get_data(element, at_sequence_id)
    return Response(
        data.SerializeToString(),
        media_type='application/x-protobuf',
    )


@router.get('/{type:element_type}/{id:int}/history/{version:int}')
async def get_version(type: ElementType, id: ElementId, version: int):
    typed_id = typed_element_id(type, id)
    versioned_typed_id = (typed_id, version)
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    elements = await ElementQuery.find_by_versioned_refs(
        [versioned_typed_id], at_sequence_id=at_sequence_id, limit=1
    )
    element = next(iter(elements), None)
    if element is None:
        raise_for.element_not_found(versioned_typed_id)

    data = await _get_data(
        element,
        at_sequence_id,
        include_parents_entries=element['latest'],
    )
    return Response(
        data.SerializeToString(),
        media_type='application/x-protobuf',
    )


@router.post('/{type:element_type}/{id:int}/history')
async def get_history(
    type: ElementType,
    id: ElementId,
    tags_diff: Annotated[bool, Query()],
    sp_state: StandardPaginationStateBody = b'',
):
    typed_id = typed_element_id(type, id)
    elements, state = await sp_paginate_query(
        Element,
        sp_state,
        select=SQL('*'),
        from_=Identifier('element'),
        where=SQL('typed_id = %s'),
        params=(typed_id,),
        cursor_key='sequence_id',
        id_key='version',
        page_size=ELEMENT_HISTORY_PAGE_SIZE,
        cursor_kind='id',
        order_dir='desc',
    )

    # HACK: Element versions are contiguous (version is 1..N), so we can treat max version as total items.
    num_items = state.snapshot_max_id
    state.num_items = num_items
    state.num_pages = sp_num_pages(
        num_items=num_items, page_size=ELEMENT_HISTORY_PAGE_SIZE
    )
    state.max_known_page = state.num_pages

    if not elements:
        page = ElementHistoryPage(elements=())
        return sp_render_response_bytes(page.SerializeToString(), state)

    at_sequence_id: SequenceId = state.u64.snapshot  # type: ignore
    changeset_ids = list({e['changeset_id'] for e in elements})

    async with TaskGroup() as tg:
        changesets_t = tg.create_task(ChangesetQuery.find_by_ids(changeset_ids))
        previous_task = (
            tg.create_task(
                ElementQuery.find_by_versioned_refs(
                    [(typed_id, elements[-1]['version'] - 1)],
                    at_sequence_id=at_sequence_id,
                    limit=1,
                )
            )
            if tags_diff
            else None
        )

    changesets = changesets_t.result()
    await UserQuery.resolve_users(changesets)
    changeset_id_map = {c['id']: c for c in changesets}

    async with TaskGroup() as tg:

        async def data_task(element: Element):
            changeset = changeset_id_map.get(element['changeset_id'])
            assert changeset is not None, 'Parent changeset must exist'
            return await _get_data(
                element,
                at_sequence_id,
                changeset=changeset,
                include_members_entries=False,
                include_parents_entries=False,
            )

        elements_tasks = [tg.create_task(data_task(element)) for element in elements]

    elements_data = [task.result() for task in elements_tasks]

    # Compute tags_old for diff mode (compare consecutive versions)
    if previous_task is not None:
        previous_element_ = previous_task.result()
        previous_tags = previous_element_[0]['tags'] if previous_element_ else None

        # Iterate in reverse (oldest to newest) to chain previous tags
        for element, element_data in zip(
            reversed(elements),
            reversed(elements_data),
            strict=True,
        ):
            if previous_tags is not None:
                element_data.tags_old.update(previous_tags)
            previous_tags = element['tags']

    page = ElementHistoryPage(elements=elements_data)
    return sp_render_response_bytes(page.SerializeToString(), state)


async def _get_data(
    element: Element,
    at_sequence_id: SequenceId,
    *,
    changeset: Changeset | None = None,
    include_members_entries: bool = True,
    include_parents_entries: bool = True,
) -> ElementData:
    typed_id = element['typed_id']
    type, id = split_typed_element_id(typed_id)
    version = element['version']

    async with TaskGroup() as tg:
        params_t = tg.create_task(
            _fetch_params(
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

    element_data = ElementData(
        type=type,
        id=id,
        version=element['version'],
        visible=element['visible'],
        name=name,
        icon=(
            ElementIcon(icon=icon.filename, title=icon.title)
            if icon is not None
            else None
        ),
        tags=element['tags'] or {},
        params=params_t.result(),
        changeset=ElementData.Changeset(
            id=element['changeset_id'],
            user=(
                ElementData.User(
                    id=changeset['user_id'],
                    display_name=user['display_name'],
                    avatar_url=user_avatar_url(user),
                )
                if (user := changeset.get('user')) is not None
                else None
            ),
            created_at=int(changeset['created_at'].timestamp()),
            comment_rich=comment_html,
        ),
        prev_version=prev_version,
        next_version=next_version,
        location=(
            ElementData.Location(lon=location[0], lat=location[1])
            if location is not None
            else None
        ),
    )

    return element_data


async def _fetch_params(
    element: Element,
    at_sequence_id: SequenceId,
    *,
    include_members_entries: bool,
    include_parents_entries: bool,
) -> PartialElementParams:
    typed_id = element['typed_id']
    type = element_type(typed_id)

    if not element['visible']:
        return PartialElementParams(
            type=type, members=(), parents=(), render=RenderElementsData()
        )

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
        return FormatElementList.element_parents(
            typed_id,
            await ElementQuery.find_parents_by_refs(
                [typed_id],
                at_sequence_id=at_sequence_id,
                limit=None,
            ),
        )

    async with TaskGroup() as tg:
        members_t = tg.create_task(members_task())
        parents = await parents_task() if include_parents_entries else ()

    members, render = members_t.result()

    return PartialElementParams(
        type=type, members=members, parents=parents, render=render
    )
