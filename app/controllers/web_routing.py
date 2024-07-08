from asyncio import TaskGroup
from typing import Annotated

from fastapi import APIRouter, Form
from shapely import get_coordinates, unary_union
from shapely.geometry.base import BaseGeometry

from app.lib.geo_utils import parse_bbox
from app.lib.message_collector import MessageCollector
from app.lib.translation import t
from app.queries.element_query import ElementQuery
from app.queries.nominatim_query import NominatimQuery

router = APIRouter(prefix='/api/web/routing')


@router.post('/resolve-names')
async def resolve_names(
    from_: Annotated[str, Form(alias='from', min_length=1)],
    to: Annotated[str, Form(min_length=1)],
    bounds: Annotated[str, Form(min_length=1)],
) -> dict:
    collector = MessageCollector()
    bounds_shape = parse_bbox(bounds)
    at_sequence_id = await ElementQuery.get_current_sequence_id()

    async with TaskGroup() as tg:
        from_task = tg.create_task(
            NominatimQuery.search(
                q=from_,
                bounds=bounds_shape,
                at_sequence_id=at_sequence_id,
                limit=1,
            )
        )
        to_task = tg.create_task(
            NominatimQuery.search(
                q=to,
                bounds=bounds_shape,
                at_sequence_id=at_sequence_id,
                limit=1,
            )
        )

    resolve_from = next(iter(from_task.result()), None)
    if resolve_from is None:
        collector.raise_error('from', t('javascripts.directions.errors.no_place', place=from_))
    resolve_to = next(iter(to_task.result()), None)
    if resolve_to is None:
        collector.raise_error('to', t('javascripts.directions.errors.no_place', place=to))

    union_bounds: BaseGeometry = unary_union((resolve_from.bounds, resolve_to.bounds))
    resolve_from_coords: list[float] = get_coordinates(resolve_from.point)[0].tolist()
    resolve_to_coords: list[float] = get_coordinates(resolve_to.point)[0].tolist()
    return {
        'from': {
            'name': resolve_from.display_name,
            'geom': resolve_from_coords,
        },
        'to': {
            'name': resolve_to.display_name,
            'geom': resolve_to_coords,
        },
        'bounds': union_bounds.bounds,
    }
