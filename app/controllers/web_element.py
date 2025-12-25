from asyncio import Task, TaskGroup
from typing import Annotated

from fastapi import APIRouter, Query, Response
from psycopg.sql import SQL, Identifier

from app.config import ELEMENT_HISTORY_PAGE_SIZE
from app.controllers.partial_element import get_element_data
from app.lib.exceptions_context import raise_for
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_num_pages,
    sp_paginate_query,
    sp_render_response_bytes,
)
from app.models.db.element import Element
from app.models.db.user import user_avatar_url
from app.models.element import ElementId, ElementType
from app.models.proto.shared_pb2 import ElementData, ElementHistoryPage, ElementIcon
from app.models.types import SequenceId
from app.queries.element_query import ElementQuery
from speedup import split_typed_element_id, typed_element_id


def _encode_element_icon(icon) -> ElementIcon | None:
    return (
        ElementIcon(icon=icon.filename, title=icon.title) if icon is not None else None
    )


def _build_element_data(data: dict) -> ElementData:
    element = data['element']
    _, id = split_typed_element_id(element['typed_id'])
    changeset = data['changeset']
    user = changeset.get('user')
    location = data['location']

    element_data = ElementData(
        type=data['params_proto'].type,
        id=id,
        version=element['version'],
        visible=element['visible'],
        name=data['name'],
        icon=_encode_element_icon(data['icon']),
        tags=data['tags'] or {},
        params=data['params_proto'],
        changeset=ElementData.Changeset(
            id=element['changeset_id'],
            user=(
                ElementData.User(
                    id=changeset['user_id'],
                    display_name=user['display_name'],
                    avatar_url=user_avatar_url(user),
                )
                if user
                else None
            ),
            created_at=int(changeset['created_at'].timestamp()),
            comment_rich=data['comment_html'],
        ),
        prev_version=data['prev_version'],
        next_version=data['next_version'],
        location=(
            ElementData.Location(lon=location[0], lat=location[1])
            if location is not None
            else None
        ),
    )

    if (tags_old := data.get('tags_old')) is not None:
        element_data.tags_old.update(tags_old)

    return element_data


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

    # if the element was superseded (very small chance), get data just before
    last_sequence_id = await ElementQuery.get_last_visible_sequence_id(element)
    if last_sequence_id is not None:
        at_sequence_id = last_sequence_id

    data = await get_element_data(element, at_sequence_id, include_parents=True)
    return Response(
        _build_element_data(data).SerializeToString(),
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

    # if the element was superseded, get data just before
    last_sequence_id = await ElementQuery.get_last_visible_sequence_id(element)
    if last_sequence_id is not None:
        at_sequence_id = last_sequence_id
        include_parents = False
    else:
        include_parents = True

    data = await get_element_data(
        element, at_sequence_id, include_parents=include_parents
    )
    return Response(
        _build_element_data(data).SerializeToString(),
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

    at_sequence_id: SequenceId = state.u64.snapshot  # type: ignore

    async with TaskGroup() as tg:
        previous_task = (
            tg.create_task(
                ElementQuery.find_by_versioned_refs(
                    [(typed_id, elements[-1]['version'] - 1)],
                    at_sequence_id=at_sequence_id,
                    limit=1,
                )
            )
            if tags_diff and elements
            else None
        )

        async def data_task(element: Element):
            at_sequence_id_ = at_sequence_id
            include_parents = True

            # if the element was superseded, get data just before
            last_sequence_id = await ElementQuery.get_last_visible_sequence_id(element)
            if last_sequence_id is not None:
                at_sequence_id_ = last_sequence_id
                include_parents = False

            return await get_element_data(
                element, at_sequence_id_, include_parents=include_parents
            )

        elements_tasks = [tg.create_task(data_task(element)) for element in elements]

    elements_data = list(map(Task.result, elements_tasks))

    if not elements_data:
        page = ElementHistoryPage(not_found=True)
        return sp_render_response_bytes(page.SerializeToString(), state)

    # Compute tags_old for diff mode (compare consecutive versions)
    if previous_task is not None:
        previous_element_ = previous_task.result()
        previous_tags = previous_element_[0]['tags'] if previous_element_ else None

        # Iterate in reverse (oldest to newest) to chain previous tags
        for data in reversed(elements_data):
            data['tags_old'] = previous_tags
            previous_tags = data['element']['tags']

    page = ElementHistoryPage(
        elements=[_build_element_data(data) for data in elements_data],
        not_found=False,
    )
    return sp_render_response_bytes(page.SerializeToString(), state)
