from asyncio import Task, TaskGroup
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import NonNegativeInt

from app.config import ELEMENT_HISTORY_PAGE_SIZE
from app.controllers.partial_element import get_element_data
from app.lib.render_response import render_response
from app.lib.standard_pagination import (
    sp_apply_headers,
    sp_resolve_page,
    standard_pagination_range,
)
from app.models.db.element import Element
from app.models.element import ElementId, ElementType
from app.queries.element_query import ElementQuery
from speedup.element_type import typed_element_id

router = APIRouter(prefix='/api/web/element')


@router.get('/{type:element_type}/{id:int}/history')
async def get_history(
    type: ElementType,
    id: ElementId,
    page: Annotated[NonNegativeInt, Query()],
    tags_diff: Annotated[bool, Query()],
    num_items: Annotated[int | None, Query()] = None,
):
    typed_id = typed_element_id(type, id)
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    sp_request_headers = num_items is None
    if sp_request_headers:
        current_version_map = await ElementQuery.map_refs_to_current_versions(
            [typed_id], at_sequence_id=at_sequence_id
        )
        num_items = current_version_map.get(typed_id, 0) or 0

    assert num_items is not None
    page = sp_resolve_page(
        page=page, num_items=num_items, page_size=ELEMENT_HISTORY_PAGE_SIZE
    )
    stmt_limit, stmt_offset = standard_pagination_range(
        page,
        page_size=ELEMENT_HISTORY_PAGE_SIZE,
        num_items=num_items,
    )
    version_max = num_items - stmt_offset
    version_min = version_max - stmt_limit + 1

    async with TaskGroup() as tg:
        previous_task = (
            tg.create_task(
                ElementQuery.find_by_versioned_refs(
                    [(typed_id, version_min - 1)],
                    at_sequence_id=at_sequence_id,
                    limit=1,
                )
            )
            if tags_diff
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

        elements = await ElementQuery.find_versions_by_ref(
            typed_id,
            at_sequence_id=at_sequence_id,
            version_range=(version_min, version_max),
            sort_dir='desc',
            limit=stmt_limit,
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

    response = await render_response(
        'partial/element-history-page',
        {
            'type': type,
            'id': id,
            'elements_data': elements_data,
            'tags_diff': tags_diff,
        },
    )

    if sp_request_headers:
        sp_apply_headers(
            response,
            num_items=num_items,
            page_size=ELEMENT_HISTORY_PAGE_SIZE,
        )

    return response
