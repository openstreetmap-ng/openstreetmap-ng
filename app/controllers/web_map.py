from typing import Annotated

from fastapi import APIRouter, Query

from app.lib.element_leaflet_formatter import format_leaflet_elements
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.limits import MAP_QUERY_AREA_MAX_SIZE, MAP_QUERY_LEGACY_NODES_LIMIT
from app.repositories.element_repository import ElementRepository

router = APIRouter(prefix='/api/web')


@router.get('/map')
async def get_map(
    bbox: Annotated[str, Query()],
):
    geometry = parse_bbox(bbox)
    if geometry.area > MAP_QUERY_AREA_MAX_SIZE:
        raise_for().map_query_area_too_big()

    elements = await ElementRepository.find_many_by_geom(
        geometry,
        nodes_limit=MAP_QUERY_LEGACY_NODES_LIMIT,
        legacy_nodes_limit=True,
    )

    return format_leaflet_elements(elements, detailed=True)
