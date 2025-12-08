from asyncio import Task, TaskGroup
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import PositiveInt

from app.config import ELEMENT_HISTORY_PAGE_SIZE
from app.controllers.partial_element import get_element_data
from app.lib.render_response import render_response
from app.lib.standard_pagination import standard_pagination_range
from app.models.db.element import Element
from app.models.element import ElementId, ElementType
from app.queries.element_query import ElementQuery
from speedup.element_type import typed_element_id

router = APIRouter(prefix='/api/web/element')


@router.get('/{type:element_type}/{id:int}/history')
async def get_history(
    type: ElementType,
    id: ElementId,
    page: Annotated[PositiveInt, Query()],
    num_items: Annotated[PositiveInt, Query()],
    tags_diff: Annotated[bool, Query()],
):
    typed_id = typed_element_id(type, id)
    at_sequence_id = await ElementQuery.get_current_sequence_id()

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

    return await render_response(
        'partial/element-history-page',
        {
            'type': type,
            'id': id,
            'elements_data': elements_data,
            'tags_diff': tags_diff,
        },
    )
