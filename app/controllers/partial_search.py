from asyncio import TaskGroup
from collections.abc import Collection
from itertools import chain
from typing import Annotated

import cython
import numpy as np
from fastapi import APIRouter, Query
from shapely import Point, lib

from app.format import FormatLeaflet
from app.lib.render_response import render_response
from app.lib.search import Search
from app.limits import (
    SEARCH_QUERY_MAX_LENGTH,
    SEARCH_RESULTS_LIMIT,
)
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.models.element_type import ElementType
from app.models.geometry import Latitude, Longitude, Zoom
from app.models.msgspec.leaflet import ElementLeaflet, ElementLeafletNode
from app.models.search_result import SearchResult
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery
from app.queries.nominatim_query import NominatimQuery
from app.utils import JSON_ENCODE

router = APIRouter(prefix='/api/partial')


@router.get('/search')
async def search(
    query: Annotated[str, Query(alias='q', min_length=1, max_length=SEARCH_QUERY_MAX_LENGTH)],
    bbox: Annotated[str, Query(min_length=1)],
    local_only: Annotated[bool, Query()] = False,
):
    search_bounds = Search.get_search_bounds(bbox, local_only=local_only)
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    async with TaskGroup() as tg:
        tasks = tuple(
            tg.create_task(
                NominatimQuery.search(
                    q=query,
                    bounds=search_bound[1],
                    at_sequence_id=at_sequence_id,
                    limit=SEARCH_RESULTS_LIMIT,
                )
            )
            for search_bound in search_bounds
        )

    task_results = tuple(task.result() for task in tasks)
    task_index = Search.best_results_index(task_results)
    bounds = search_bounds[task_index][0]
    results = Search.deduplicate_similar_results(task_results[task_index])
    return await _get_response(
        at_sequence_id=at_sequence_id,
        bounds=bounds,
        results=results,
    )


@router.get('/where-is-this')
async def where_is_this(
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    zoom: Annotated[Zoom, Query()],
):
    result = await NominatimQuery.reverse(Point(lon, lat), zoom)
    return await _get_response(
        at_sequence_id=None,
        bounds='',
        results=(result,),
    )


async def _get_response(*, at_sequence_id: int | None, bounds: str, results: Collection[SearchResult]):
    elements = tuple(r.element for r in results)
    await ElementMemberQuery.resolve_members(elements)

    members_refs = {ElementRef(member.type, member.id) for element in elements for member in element.members}  # type: ignore[union-attr]
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

    Search.improve_point_accuracy(results, members_map)
    Search.remove_overlapping_points(results)

    # prepare data for leaflet rendering
    leaflet: list[list[ElementLeaflet]] = [None] * len(results)  # type: ignore[list-item]

    i: cython.int
    for i, result in enumerate(results):
        element = result.element
        element_members = tuple(members_map[member.type, member.id] for member in element.members)  # type: ignore[union-attr]
        full_data = chain(
            (element,),
            element_members,
            (
                members_map[mm.type, mm.id]
                for member in element_members
                if member.type == 'way'  # recurse_ways
                for mm in member.members  # type: ignore[union-attr]
            ),
        )

        leaflet_elements = FormatLeaflet.encode_elements(full_data, detailed=False, areas=False)

        # ensure there is always a node, it's nice visually
        if not any(leaflet_element.type == 'node' for leaflet_element in leaflet_elements):
            x, y = lib.get_coordinates(np.asarray(result.point, dtype=object), False, False)[0].tolist()
            leaflet_elements.append(ElementLeafletNode('node', 0, [y, x]))

        leaflet[i] = leaflet_elements

    return render_response(
        'partial/search.jinja2',
        {
            'bounds': bounds,
            'results': results,
            'leaflet': JSON_ENCODE(leaflet).decode(),
        },
    )
