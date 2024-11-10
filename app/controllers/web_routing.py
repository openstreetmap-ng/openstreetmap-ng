from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Form, Response
from shapely import Point, get_coordinates
from starlette import status

from app.lib.geo_utils import try_parse_point
from app.lib.search import Search
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.geometry import Latitude, Longitude
from app.models.proto.shared_pb2 import RoutingResult, SharedBounds
from app.queries.element_query import ElementQuery
from app.queries.graphhopper_query import GraphHopperProfiles, GraphHopperQuery
from app.queries.nominatim_query import NominatimQuery
from app.queries.osrm_query import OSRMProfiles, OSRMQuery
from app.queries.valhalla_query import ValhallaProfiles, ValhallaQuery

router = APIRouter(prefix='/api/web/routing')


@router.post('')
async def route(
    bbox: Annotated[str, Form(min_length=1)],
    start: Annotated[str, Form(min_length=1)],
    start_loaded: Annotated[str, Form()],
    start_loaded_lon: Annotated[Longitude, Form()],
    start_loaded_lat: Annotated[Latitude, Form()],
    end: Annotated[str, Form(min_length=1)],
    end_loaded: Annotated[str, Form()],
    end_loaded_lon: Annotated[Longitude, Form()],
    end_loaded_lat: Annotated[Latitude, Form()],
    engine: Annotated[str, Form(min_length=1)],
):
    start_endpoint, end_endpoint = await _resolve_names(bbox, start, start_loaded, end, end_loaded)
    if start_endpoint is not None:
        start_loaded_lon = start_endpoint.lon
        start_loaded_lat = start_endpoint.lat
    if end_endpoint is not None:
        end_loaded_lon = end_endpoint.lon
        end_loaded_lat = end_endpoint.lat
    start_point = Point(start_loaded_lon, start_loaded_lat)
    end_point = Point(end_loaded_lon, end_loaded_lat)

    engine, _, profile = engine.partition('_')
    if engine == 'graphhopper' and profile in GraphHopperProfiles:
        result = await GraphHopperQuery.route(start_point, end_point, profile=profile)
    elif engine == 'osrm' and profile in OSRMProfiles:
        result = await OSRMQuery.route(start_point, end_point, profile=profile)
    elif engine == 'valhalla' and profile in ValhallaProfiles:
        result = await ValhallaQuery.route(start_point, end_point, profile=profile)
    else:
        return Response(f'Unsupported engine profile: {engine}_{profile}', status.HTTP_400_BAD_REQUEST)

    if start_endpoint is not None:
        result.MergeFrom(RoutingResult(start=start_endpoint))
    if end_endpoint is not None:
        result.MergeFrom(RoutingResult(end=end_endpoint))
    return Response(result.SerializeToString(), media_type='application/x-protobuf')


async def _resolve_names(bbox: str, start: str, start_loaded: str, end: str, end_loaded: str):
    at_sequence_id = await ElementQuery.get_current_sequence_id()
    async with TaskGroup() as tg:
        from_task = (
            tg.create_task(_resolve_name('start', start, bbox, at_sequence_id))
            if (start != start_loaded)  #
            else None
        )
        to_task = (
            tg.create_task(_resolve_name('end', end, bbox, at_sequence_id))
            if (end != end_loaded)  #
            else None
        )
    resolve_from = from_task.result() if (from_task is not None) else None
    resolve_to = to_task.result() if (to_task is not None) else None
    return resolve_from, resolve_to


async def _resolve_name(field: str, query: str, bbox: str, at_sequence_id: int) -> RoutingResult.Endpoint:
    # try to parse as literal point
    point = try_parse_point(query)
    if point is not None:
        x, y = get_coordinates(point)[0].tolist()
        return RoutingResult.Endpoint(
            name=query,
            bounds=SharedBounds(min_lon=x, min_lat=y, max_lon=x, max_lat=y),
            lon=x,
            lat=y,
        )

    # fallback to nominatim search
    search_bounds = Search.get_search_bounds(bbox, local_max_iterations=1)

    async with TaskGroup() as tg:
        tasks = tuple(
            tg.create_task(
                NominatimQuery.search(
                    q=query,
                    bounds=search_bound[1],
                    at_sequence_id=at_sequence_id,
                    limit=1,
                )
            )
            for search_bound in search_bounds
        )

    task_results = tuple(task.result() for task in tasks)
    task_index = Search.best_results_index(task_results)
    results = task_results[task_index]
    if not results:
        StandardFeedback.raise_error(field, t('javascripts.directions.errors.no_place', place=query))

    result = results[0]
    bounds = result.bounds
    x, y = get_coordinates(result.point)[0].tolist()
    return RoutingResult.Endpoint(
        name=result.display_name,
        bounds=SharedBounds(
            min_lon=bounds[0],
            min_lat=bounds[1],
            max_lon=bounds[2],
            max_lat=bounds[3],
        ),
        lon=x,
        lat=y,
    )
