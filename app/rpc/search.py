from asyncio import TaskGroup
from typing import override

from connectrpc.request import RequestContext
from shapely import Point, get_coordinates

from app.config import SEARCH_RESULTS_LIMIT
from app.format import FormatRender
from app.lib.search import Search, SearchResult
from app.models.db.element import Element
from app.models.element import (
    TYPED_ELEMENT_ID_WAY_MAX,
    TYPED_ELEMENT_ID_WAY_MIN,
    TypedElementId,
)
from app.models.proto.element_pb2 import RenderElementsData
from app.models.proto.search_connect import SearchService, SearchServiceASGIApplication
from app.models.proto.search_pb2 import (
    ReverseRequest,
    ReverseResponse,
    SearchData,
    SearchRequest,
    SearchResponse,
)
from app.models.proto.shared_pb2 import Bounds, ElementIcon, LonLat
from app.models.types import SequenceId
from app.queries.element_query import ElementQuery
from app.queries.nominatim_query import NominatimQuery
from speedup import split_typed_element_id


class _Service(SearchService):
    @override
    async def search(
        self, request: SearchRequest, ctx: RequestContext
    ) -> SearchResponse:
        bbox_str = _bbox_to_string(request.bbox)
        search_bounds = Search.get_search_bounds(
            bbox_str, local_only=request.local_only
        )
        at_sequence_id = await ElementQuery.get_current_sequence_id()

        async with TaskGroup() as tg:
            results_t = [
                tg.create_task(
                    NominatimQuery.search(
                        q=request.query,
                        bounds=search_bound[1],
                        at_sequence_id=at_sequence_id,
                        limit=SEARCH_RESULTS_LIMIT,
                    )
                )
                for search_bound in search_bounds
            ]
        results_by_bound = [t.result() for t in results_t]

        best_index = Search.best_results_index(results_by_bound)
        bounds_str = search_bounds[best_index][0]
        results = Search.deduplicate_similar_results(results_by_bound[best_index])

        return SearchResponse(
            data=await _build_search_data(
                at_sequence_id=at_sequence_id,
                bounds_str=bounds_str,
                results=results,
            )
        )

    @override
    async def reverse(
        self, request: ReverseRequest, ctx: RequestContext
    ) -> ReverseResponse:
        at = request.at
        result = await NominatimQuery.reverse(Point(at.lon, at.lat), at.zoom)
        results = [result] if result is not None else []

        return ReverseResponse(
            data=await _build_search_data(
                at_sequence_id=None,
                bounds_str=None,
                results=results,
            )
        )


service = _Service()
asgi_app_cls = SearchServiceASGIApplication


def _bbox_to_string(bbox: Bounds):
    return (
        f'{bbox.min_lon:.7f},{bbox.min_lat:.7f},{bbox.max_lon:.7f},{bbox.max_lat:.7f}'
    )


async def _build_search_data(
    *,
    at_sequence_id: SequenceId | None,
    bounds_str: str | None,
    results: list[SearchResult],
):
    members: list[TypedElementId] = [
        member
        for result in results
        if (result_members := result.element['members'])
        for member in result_members
    ]

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
            if TYPED_ELEMENT_ID_WAY_MIN <= member_tid <= TYPED_ELEMENT_ID_WAY_MAX:
                full_data.extend(
                    e
                    for mm in member['members'] or ()
                    if (e := members_map.get(mm)) is not None
                )

        render = FormatRender.encode_elements(full_data, detailed=False, areas=False)

        # Ensure there is always a node. It's nice visually.
        if not render.nodes:
            render.nodes.append(
                RenderElementsData.Node(id=0, location=LonLat(lon=x, lat=y))
            )

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
                location=LonLat(lon=x, lat=y),
            )
        )

    if bounds_str is not None:
        min_lon, min_lat, max_lon, max_lat = map(float, bounds_str.split(',', 3))
        bounds = Bounds(
            min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat
        )
    else:
        bounds = None

    return SearchData(bounds=bounds, results=response_results)
