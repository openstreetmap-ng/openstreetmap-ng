from typing import Annotated

from anyio import create_task_group
from fastapi import APIRouter, Form
from shapely import get_coordinates, unary_union
from shapely.geometry.base import BaseGeometry

from app.lib.geo_utils import parse_bbox
from app.lib.nominatim import Nominatim
from app.models.nominatim_result import NominatimResult

router = APIRouter(prefix='/api/web/routing')


@router.post('/resolve-names')
async def resolve_names(
    from_: Annotated[str, Form(alias='from', min_length=1)],
    to: Annotated[str, Form(min_length=1)],
    bounds: Annotated[str, Form(min_length=1)],
) -> dict:
    bounds_shape = parse_bbox(bounds)  # TODO: MultiPolygon support
    resolve_from: NominatimResult = None
    resolve_to: NominatimResult = None

    async def from_task() -> None:
        nonlocal resolve_from
        resolve_from = await Nominatim.search(q=from_, bounds=bounds_shape)

    async def to_task() -> None:
        nonlocal resolve_to
        resolve_to = await Nominatim.search(q=to, bounds=bounds_shape)

    async with create_task_group() as tg:
        tg.start_soon(from_task)
        tg.start_soon(to_task)

    union_bounds: BaseGeometry = unary_union((resolve_from.bounds, resolve_to.bounds))
    resolve_from_coords: list[float] = get_coordinates(resolve_from.point)[0].tolist()
    resolve_to_coords: list[float] = get_coordinates(resolve_to.point)[0].tolist()

    return {
        'from': {
            'name': resolve_from.name,
            'point': resolve_from_coords,
        },
        'to': {
            'name': resolve_to.name,
            'point': resolve_to_coords,
        },
        'bounds': union_bounds.bounds,
    }
