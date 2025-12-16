from asyncio import Task, TaskGroup
from typing import Annotated

from fastapi import APIRouter, Query
from psycopg.sql import SQL, Identifier

from app.config import ELEMENT_HISTORY_PAGE_SIZE
from app.controllers.partial_element import get_element_data
from app.lib.standard_pagination import (
    StandardPaginationStateBody,
    sp_num_pages,
    sp_paginate_query,
    sp_render_response,
)
from app.models.db.element import Element
from app.models.element import ElementId, ElementType
from app.models.types import SequenceId
from app.queries.element_query import ElementQuery
from speedup.element_type import typed_element_id

router = APIRouter(prefix='/api/web/element')


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

    # Compute tags_old for diff mode (compare consecutive versions)
    if previous_task is not None:
        previous_element_ = previous_task.result()
        previous_tags = previous_element_[0]['tags'] if previous_element_ else None

        # Iterate in reverse (oldest to newest) to chain previous tags
        for data in reversed(elements_data):
            data['tags_old'] = previous_tags
            previous_tags = data['element']['tags']

    return await sp_render_response(
        'partial/element-history-page',
        {
            'type': type,
            'id': id,
            'elements_data': elements_data,
            'tags_diff': tags_diff,
        },
        state,
    )
