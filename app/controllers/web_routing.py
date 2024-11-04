from asyncio import TaskGroup
from collections.abc import Sequence
from typing import Annotated, NamedTuple

from fastapi import APIRouter, Form
from shapely import Polygon, box, get_coordinates

from app.lib.geo_utils import try_parse_point
from app.lib.search import Search
from app.lib.standard_feedback import StandardFeedback
from app.lib.translation import t
from app.queries.element_query import ElementQuery
from app.queries.nominatim_query import NominatimQuery


class _ResolveResult(NamedTuple):
    bounds: Polygon
    coords: Sequence[float]
    display_name: str


router = APIRouter(prefix='/api/web/routing')


@router.post('/resolve-names')
async def resolve_names(
    from_: Annotated[str, Form(alias='from', min_length=1)],
    to: Annotated[str, Form(min_length=1)],
    bbox: Annotated[str, Form(min_length=1)],
    from_loaded: Annotated[str, Form()] = '',
    to_loaded: Annotated[str, Form()] = '',
) -> dict:
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    async with TaskGroup() as tg:
        from_task = (
            tg.create_task(_resolve_name('from', from_, bbox, at_sequence_id))  #
            if (from_ != from_loaded)
            else None
        )
        to_task = (
            tg.create_task(_resolve_name('to', to, bbox, at_sequence_id))  #
            if (to != to_loaded)
            else None
        )

    resolve_from = from_task.result() if (from_task is not None) else None
    resolve_to = to_task.result() if (to_task is not None) else None
    response = {}
    if resolve_from is not None:
        response['from'] = {
            'bounds': resolve_from.bounds.bounds,
            'geom': resolve_from.coords,
            'name': resolve_from.display_name,
        }
    if resolve_to is not None:
        response['to'] = {
            'bounds': resolve_to.bounds.bounds,
            'geom': resolve_to.coords,
            'name': resolve_to.display_name,
        }
    return response


async def _resolve_name(field: str, query: str, bbox: str, at_sequence_id: int) -> _ResolveResult:
    # try to parse as literal point
    point = try_parse_point(query)
    if point is not None:
        x, y = get_coordinates(point)[0].tolist()
        return _ResolveResult(
            bounds=box(x, y, x, y),
            coords=(x, y),
            display_name=query,
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
    coords = get_coordinates(result.point)[0].tolist()
    return _ResolveResult(
        bounds=result.bounds,
        coords=coords,
        display_name=result.display_name,
    )
