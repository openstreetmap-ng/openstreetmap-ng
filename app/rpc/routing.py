from asyncio import Task, TaskGroup
from typing import Any, Protocol, override

from connectrpc.request import RequestContext
from shapely import Point, get_coordinates

from app.lib.geo_utils import try_parse_point
from app.lib.search import Search, SearchResult
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.proto.routing_connect import (
    RoutingService as RoutingServiceConnect,
)
from app.models.proto.routing_connect import (
    RoutingServiceASGIApplication,
)
from app.models.proto.routing_pb2 import GetRouteRequest, GetRouteResponse
from app.models.proto.shared_pb2 import Bounds, LonLat, RoutingResult
from app.models.types import SequenceId
from app.queries.element_query import ElementQuery
from app.queries.graphhopper_query import GraphHopperQuery
from app.queries.nominatim_query import NominatimQuery
from app.queries.osrm_query import OSRMQuery
from app.queries.valhalla_query import ValhallaQuery


class _Service(RoutingServiceConnect):
    @override
    async def get_route(self, request: GetRouteRequest, ctx: RequestContext):
        at_sequence_id = await ElementQuery.get_current_sequence_id()
        async with TaskGroup() as tg:
            start_t = tg.create_task(
                _resolve_endpoint(
                    'start',
                    endpoint=request.start,
                    bbox=request.bbox,
                    at_sequence_id=at_sequence_id,
                )
            )
            end_t = tg.create_task(
                _resolve_endpoint(
                    'end',
                    endpoint=request.end,
                    bbox=request.bbox,
                    at_sequence_id=at_sequence_id,
                )
            )

        start_endpoint = start_t.result()
        start_point = Point(start_endpoint.location.lon, start_endpoint.location.lat)
        end_endpoint = end_t.result()
        end_point = Point(end_endpoint.location.lon, end_endpoint.location.lat)

        route_fn, profile = _ENGINE_TABLE[request.engine]
        result = await route_fn(start_point, end_point, profile=profile)
        result.MergeFrom(RoutingResult(start=start_endpoint, end=end_endpoint))
        return GetRouteResponse(route=result)


async def _resolve_name(
    field: str,
    query: str,
    bbox: Bounds,
    at_sequence_id: SequenceId,
):
    point = try_parse_point(query)
    if point is not None:
        x, y = get_coordinates(point)[0].tolist()
        return RoutingResult.Endpoint(
            name=query,
            bounds=Bounds(min_lon=x, min_lat=y, max_lon=x, max_lat=y),
            location=LonLat(lon=x, lat=y),
        )

    search_bounds = Search.get_search_bounds(bbox, local_max_iterations=1)

    async with TaskGroup() as tg:
        tasks = [
            tg.create_task(
                NominatimQuery.search(
                    q=query,
                    bounds=search_bound[1],
                    at_sequence_id=at_sequence_id,
                    limit=1,
                )
            )
            for search_bound in search_bounds
        ]

    task_results: list[list[SearchResult]]
    task_results = list(map(Task.result, tasks))

    task_index = Search.best_results_index(task_results)
    results = task_results[task_index]
    result = next(iter(results), None)
    if result is None:
        StandardFeedback.raise_error(
            field, t('javascripts.directions.errors.no_place', place=query)
        )

    x = float(result.point.x)
    y = float(result.point.y)
    min_lon, min_lat, max_lon, max_lat = result.bounds
    return RoutingResult.Endpoint(
        name=result.display_name,
        bounds=Bounds(
            min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat
        ),
        location=LonLat(lon=x, lat=y),
    )


async def _resolve_endpoint(
    field: str,
    *,
    endpoint: GetRouteRequest.EndpointInput,
    bbox: Bounds,
    at_sequence_id: SequenceId,
):
    query = endpoint.query

    if not endpoint.HasField('location'):
        return await _resolve_name(field, query, bbox, at_sequence_id)

    location = endpoint.location
    return RoutingResult.Endpoint(
        name=endpoint.label or query,
        bounds=(
            endpoint.bounds
            if endpoint.HasField('bounds')
            else Bounds(
                min_lon=location.lon,
                min_lat=location.lat,
                max_lon=location.lon,
                max_lat=location.lat,
            )
        ),
        location=location,
    )


class _Route(Protocol):
    @staticmethod
    async def __call__(start: Point, end: Point, *, profile: Any) -> RoutingResult: ...


_ENGINE_TABLE: dict[int, tuple[_Route, str]] = {
    GetRouteRequest.Engine.graphhopper_car: (GraphHopperQuery.route, 'car'),
    GetRouteRequest.Engine.graphhopper_bike: (GraphHopperQuery.route, 'bike'),
    GetRouteRequest.Engine.graphhopper_foot: (GraphHopperQuery.route, 'foot'),
    GetRouteRequest.Engine.osrm_car: (OSRMQuery.route, 'car'),
    GetRouteRequest.Engine.osrm_bike: (OSRMQuery.route, 'bike'),
    GetRouteRequest.Engine.osrm_foot: (OSRMQuery.route, 'foot'),
    GetRouteRequest.Engine.valhalla_auto: (ValhallaQuery.route, 'auto'),
    GetRouteRequest.Engine.valhalla_bicycle: (ValhallaQuery.route, 'bicycle'),
    GetRouteRequest.Engine.valhalla_pedestrian: (ValhallaQuery.route, 'pedestrian'),
}


service = _Service()
asgi_app_cls = RoutingServiceASGIApplication
