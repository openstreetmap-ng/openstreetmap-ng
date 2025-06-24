from asyncio import TaskGroup
from base64 import urlsafe_b64encode
from typing import Annotated

import cython
from fastapi import APIRouter, Query
from shapely import Point, get_coordinates

from app.config import SEARCH_QUERY_MAX_LENGTH, SEARCH_RESULTS_LIMIT
from app.format import FormatLeaflet
from app.lib.render_response import render_response
from app.lib.search import Search, SearchResult
from app.models.db.element import Element
from app.models.element import (
    TYPED_ELEMENT_ID_WAY_MAX,
    TYPED_ELEMENT_ID_WAY_MIN,
    TypedElementId,
)
from app.models.proto.shared_pb2 import PartialSearchParams, RenderElementsData
from app.models.types import Latitude, Longitude, SequenceId, Zoom
from app.queries.element_query import ElementQuery
from app.queries.nominatim_query import NominatimQuery

router = APIRouter(prefix='/partial')


@router.get('/search')
async def get_search(
    query: Annotated[
        str, Query(alias='q', min_length=1, max_length=SEARCH_QUERY_MAX_LENGTH)
    ],
    bbox: Annotated[str, Query(min_length=1)],
    local_only: Annotated[bool, Query()] = False,
):
    search_bounds = Search.get_search_bounds(bbox, local_only=local_only)
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    async with TaskGroup() as tg:
        tasks = [
            tg.create_task(
                NominatimQuery.search(
                    q=query,
                    bounds=search_bound[1],
                    at_sequence_id=at_sequence_id,
                    limit=SEARCH_RESULTS_LIMIT,
                )
            )
            for search_bound in search_bounds
        ]

    results = [task.result() for task in tasks]
    best_index = Search.best_results_index(results)
    bounds = search_bounds[best_index][0]
    results = Search.deduplicate_similar_results(results[best_index])

    return await _get_response(
        at_sequence_id=at_sequence_id,
        bounds=bounds,
        results=results,
        where_is_this=False,
    )


@router.get('/where-is-this')
async def get_where_is_this(
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    zoom: Annotated[Zoom, Query()],
):
    result = await NominatimQuery.reverse(Point(lon, lat), zoom)
    results = [result] if result is not None else []
    return await _get_response(
        at_sequence_id=None,
        bounds=None,
        results=results,
        where_is_this=True,
    )


async def _get_response(
    *,
    at_sequence_id: SequenceId | None,
    bounds: str | None,
    results: list[SearchResult],
    where_is_this: bool,
):
    members: list[TypedElementId] = [
        member
        for result in results
        if (result_members := result.element['members'])
        for member in result_members
    ]
    members_elements = await ElementQuery.get_by_refs(
        members,
        at_sequence_id=at_sequence_id,
        recurse_ways=True,
        limit=None,
    )

    members_map: dict[TypedElementId, Element] = {
        member['typed_id']: member for member in members_elements
    }
    Search.improve_point_accuracy(results, members_map)
    Search.remove_overlapping_points(results)

    # prepare data for rendering
    renders: list[RenderElementsData] = [None] * len(results)  # type: ignore

    typed_element_id_way_min: cython.ulonglong = TYPED_ELEMENT_ID_WAY_MIN
    typed_element_id_way_max: cython.ulonglong = TYPED_ELEMENT_ID_WAY_MAX

    i: cython.Py_ssize_t
    for i, result in enumerate(results):
        result_element = result.element
        full_data: list[Element] = [result_element]

        result_members = result_element['members']
        if result_members:
            for member in result_members:
                member_element = members_map[member]
                full_data.append(member_element)

                member_members = member_element['members']
                if not member_members:
                    continue

                typed_id: cython.ulonglong = member_element['typed_id']
                if (
                    typed_id < typed_element_id_way_min
                    or typed_id > typed_element_id_way_max
                ):
                    continue

                # Recurse ways
                full_data.extend(members_map[mm] for mm in member_members)

        render = FormatLeaflet.encode_elements(full_data, detailed=False, areas=False)
        renders[i] = render

        # Ensure there is always a node. It's nice visually.
        if not render.nodes:
            x, y = get_coordinates(result.point)[0].tolist()
            render.nodes.append(RenderElementsData.Node(id=0, lon=x, lat=y))

    params = PartialSearchParams(
        bounds_str=bounds,
        renders=renders,
        where_is_this=where_is_this,
    )

    return await render_response(
        'partial/search',
        {
            'results': results,
            'params': urlsafe_b64encode(params.SerializeToString()).decode(),
        },
    )
