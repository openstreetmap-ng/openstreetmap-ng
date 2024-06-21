from collections.abc import Sequence
from itertools import chain
from typing import Annotated

from anyio import create_task_group
from fastapi import APIRouter, Query

from app.format import FormatLeaflet
from app.lib.geo_utils import parse_bbox
from app.lib.nominatim import Nominatim
from app.lib.render_response import render_response
from app.limits import SEARCH_QUERY_MAX_LENGTH, SEARCH_RESULTS_LIMIT
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.models.element_type import ElementType
from app.models.msgspec.leaflet import ElementLeaflet
from app.models.nominatim_result import NominatimResult
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/api/partial/search')


@router.get('/')
async def search(
    query: Annotated[str, Query(alias='q', min_length=1, max_length=SEARCH_QUERY_MAX_LENGTH)],
    bbox: Annotated[str, Query(min_length=1)],
    local_only: Annotated[bool, Query()] = False,
):
    geometry = parse_bbox(bbox)  # TODO: MultiPolygon handling
    global_results: Sequence[NominatimResult] = ()
    local_results: Sequence[NominatimResult] = ()
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    # TODO: update results when map moves -> local_only
    # TODO: search this area -> local_only

    async def global_task():
        nonlocal global_results
        global_results = await Nominatim.search_elements(
            q=query,
            at_sequence_id=at_sequence_id,
            limit=SEARCH_RESULTS_LIMIT,
        )

    async def local_task():
        nonlocal local_results
        local_results = await Nominatim.search_elements(
            q=query,
            bounds=geometry,
            at_sequence_id=at_sequence_id,
            limit=SEARCH_RESULTS_LIMIT,
        )

    async with create_task_group() as tg:
        if not local_only:
            tg.start_soon(global_task)
        tg.start_soon(local_task)

    # TODO: prioritize global vs local results, use rank and importance
    results = chain(global_results, local_results)
    results = Nominatim.deduplicate_similar_results(results)

    elements = tuple(r.element for r in results)
    await ElementMemberQuery.resolve_members(elements)

    members_refs = {
        ElementRef(member.type, member.id)
        for element in elements
        if element.members is not None
        for member in element.members
    }
    members_elements = await ElementQuery.get_by_refs(
        members_refs,
        at_sequence_id=at_sequence_id,
        recurse_ways=True,
        limit=None,
    )
    members_map: dict[tuple[ElementType, int], Element] = {
        (member.type, member.id): member  #
        for member in members_elements
    }

    Nominatim.improve_point_accuracy(results, members_map)
    Nominatim.remove_overlapping_points(results)

    # prepare data for leaflet rendering
    leaflet: list[list[ElementLeaflet]] = []
    for element in elements:
        if element.members is None:
            full_data = (element,)
        else:
            full_data = [element, *(members_map[member.type, member.id] for member in element.members)]
            full_data.extend(
                members_map[member_.type, member_.id]
                for member in full_data[1:]
                if member.type == 'way'  # recurse_ways
                for member_ in member.members
            )
        leaflet.append(FormatLeaflet.encode_elements(full_data, detailed=False))

    return render_response(
        'partial/search.jinja2',
        {
            'results': results,
            'leaflet': JSON_ENCODE(leaflet).decode(),
        },
    )
