from asyncio import Task, TaskGroup
from typing import Annotated

import cython
from fastapi import APIRouter, Query, Response
from shapely import Point, get_coordinates

from app.config import SEARCH_QUERY_MAX_LENGTH, SEARCH_RESULTS_LIMIT
from app.format import FormatRender
from app.lib.search import Search, SearchResult
from app.models.db.element import Element
from app.models.element import (
    TYPED_ELEMENT_ID_WAY_MAX,
    TYPED_ELEMENT_ID_WAY_MIN,
    TypedElementId,
)
from app.models.proto.shared_pb2 import (
    ElementIcon,
    RenderElementsData,
    SearchData,
    SharedBounds,
)
from app.models.types import Latitude, Longitude, SequenceId, Zoom
from app.queries.element_query import ElementQuery
from app.queries.nominatim_query import NominatimQuery
from speedup import split_typed_element_id

router = APIRouter(prefix='/api/web/search')


@router.get('/results')
async def get_search_results(
    query: Annotated[
        str, Query(alias='q', min_length=1, max_length=SEARCH_QUERY_MAX_LENGTH)
    ],
    bbox: Annotated[str, Query(min_length=1)],
    local_only: Annotated[bool, Query()] = False,
):
    search_bounds = Search.get_search_bounds(bbox, local_only=local_only)
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    async with TaskGroup() as tg:
        tasks: list[Task[list[SearchResult]]] = [
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

    results = list(map(Task.result, tasks))
    best_index = Search.best_results_index(results)
    bounds_str = search_bounds[best_index][0]
    results = Search.deduplicate_similar_results(results[best_index])

    data = await _build_search_data(
        at_sequence_id=at_sequence_id,
        bounds_str=bounds_str,
        results=results,
    )
    return Response(data.SerializeToString(), media_type='application/x-protobuf')


@router.get('/where-is-this')
async def get_where_is_this(
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    zoom: Annotated[Zoom, Query()],
):
    result = await NominatimQuery.reverse(Point(lon, lat), zoom)
    results = [result] if result is not None else []

    data = await _build_search_data(
        at_sequence_id=None,
        bounds_str=None,
        results=results,
    )
    return Response(data.SerializeToString(), media_type='application/x-protobuf')


async def _build_search_data(
    *,
    at_sequence_id: SequenceId | None,
    bounds_str: str | None,
    results: list[SearchResult],
    TYPED_ELEMENT_ID_WAY_MIN: cython.size_t = TYPED_ELEMENT_ID_WAY_MIN,
    TYPED_ELEMENT_ID_WAY_MAX: cython.size_t = TYPED_ELEMENT_ID_WAY_MAX,
):
    members: list[TypedElementId] = [
        member
        for result in results
        if (result_members := result.element['members'])
        for member in result_members
    ]
    members_map: dict[TypedElementId, Element]
    members_map = {
        member['typed_id']: member
        for member in await ElementQuery.find_by_refs(
            members,
            at_sequence_id=at_sequence_id,
            recurse_ways=True,
            limit=None,
        )
    }
    Search.improve_point_accuracy(results, members_map)
    Search.remove_overlapping_points(results)

    response_results: list[SearchData.Result] = []
    for result in results:
        x, y = get_coordinates(result.point)[0].tolist()

        full_data: list[Element] = [result.element]
        for member_tid in result.element['members'] or ():
            member = members_map.get(member_tid)
            if member is None:
                continue
            full_data.append(member)

            # Recurse ways
            typed_id: cython.size_t = member_tid
            if TYPED_ELEMENT_ID_WAY_MIN <= typed_id <= TYPED_ELEMENT_ID_WAY_MAX:
                full_data.extend(
                    e
                    for mm in member['members'] or ()
                    if (e := members_map.get(mm)) is not None
                )

        render = FormatRender.encode_elements(full_data, detailed=False, areas=False)

        # Ensure there is always a node. It's nice visually.
        if not render.nodes:
            render.nodes.append(RenderElementsData.Node(id=0, lon=x, lat=y))

        type, id = split_typed_element_id(result.element['typed_id'])
        icon = (
            ElementIcon(icon=result.icon.filename, title=result.icon.title)
            if result.icon is not None
            else None
        )

        response_results.append(
            SearchData.Result(
                type=type,
                id=id,
                prefix=result.prefix,
                display_name=result.display_name,
                icon=icon,
                render=render,
                lon=x,
                lat=y,
            )
        )

    if bounds_str is not None:
        min_lon_s, min_lat_s, max_lon_s, max_lat_s = bounds_str.split(',', 3)
        bounds = SharedBounds(
            min_lon=float(min_lon_s),
            min_lat=float(min_lat_s),
            max_lon=float(max_lon_s),
            max_lat=float(max_lat_s),
        )
    else:
        bounds = None

    return SearchData(bounds=bounds, results=response_results)
