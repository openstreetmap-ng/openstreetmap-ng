from typing import Annotated, Sequence

from fastapi import APIRouter, Query

from geoutils import parse_bbox
from lib.exceptions import Exceptions
from lib.format.format06 import Format06
from lib.xmltodict import XAttr
from limits import MAP_QUERY_AREA_MAX_SIZE, MAP_QUERY_LEGACY_NODES_LIMIT
from models.collections.element import Element
from models.str import NonEmptyStr

router = APIRouter()


@router.get('/map')
@router.get('/map.xml')
@router.get('/map.json')
async def map_read(bbox: Annotated[NonEmptyStr, Query()]) -> Sequence[dict]:
    geometry = parse_bbox(bbox)
    if geometry.area > MAP_QUERY_AREA_MAX_SIZE:
        Exceptions.get().raise_for_map_query_area_too_big()

    elements = await Element.find_many_by_query(
        geometry,
        nodes_limit=MAP_QUERY_LEGACY_NODES_LIMIT,
        legacy_nodes_limit=True)

    minx, miny, maxx, maxy = geometry
    return {
        'bounds': {
            XAttr('minlon'): minx,
            XAttr('minlat'): miny,
            XAttr('maxlon'): maxx,
            XAttr('maxlat'): maxy,
        },
        **Format06.encode_elements(elements),
    }
