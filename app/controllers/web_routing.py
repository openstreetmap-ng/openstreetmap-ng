from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Query, Response
from shapely import Point, get_coordinates
from starlette import status

from app.lib.geo_utils import try_parse_point
from app.lib.search import Search
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.models.geometry import Latitude, Longitude
from app.models.proto.shared_pb2 import RoutingResolveNames, SharedBounds
from app.queries.element_query import ElementQuery
from app.queries.graphhopper_query import GraphHopperProfiles, GraphHopperQuery
from app.queries.nominatim_query import NominatimQuery
from app.queries.osrm_query import OSRMProfiles, OSRMQuery
from app.queries.valhalla_query import ValhallaProfiles, ValhallaQuery

router = APIRouter(prefix='/api/web/routing')


@router.get('/route')
async def route(
    engine: Annotated[str, Query(min_length=1)],
    start_lon: Longitude,
    start_lat: Latitude,
    end_lon: Longitude,
    end_lat: Latitude,
):
    engine, _, profile = engine.partition('_')
    start = Point(start_lon, start_lat)
    end = Point(end_lon, end_lat)
    result: bytes | None = None
    if engine == 'graphhopper' and profile in GraphHopperProfiles:
        result = (await GraphHopperQuery.route(start, end, profile=profile)).SerializeToString()
    elif engine == 'osrm' and profile in OSRMProfiles:
        result = (await OSRMQuery.route(start, end, profile=profile)).SerializeToString()
    elif engine == 'valhalla' and profile in ValhallaProfiles:
        result = (await ValhallaQuery.route(start, end, profile=profile)).SerializeToString()

    if result is None:
        return Response(f'Unsupported engine profile: {engine}_{profile}', status.HTTP_400_BAD_REQUEST)
    return Response(result, media_type='application/x-protobuf')


@router.get('/resolve-names')
async def resolve_names(
    start: Annotated[str, Query(min_length=1)],
    end: Annotated[str, Query(min_length=1)],
    bbox: Annotated[str, Query(min_length=1)],
    start_loaded: Annotated[str, Query()] = '',
    end_loaded: Annotated[str, Query()] = '',
):
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
    return Response(
        RoutingResolveNames(start=resolve_from, end=resolve_to).SerializeToString(),
        media_type='application/x-protobuf',
    )


async def _resolve_name(field: str, query: str, bbox: str, at_sequence_id: int) -> RoutingResolveNames.Entry:
    # try to parse as literal point
    point = try_parse_point(query)
    if point is not None:
        x, y = get_coordinates(point)[0].tolist()
        return RoutingResolveNames.Entry(
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
    bounds = result.bounds.bounds
    x, y = get_coordinates(result.point)[0].tolist()
    return RoutingResolveNames.Entry(
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
