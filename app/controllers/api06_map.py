from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy.orm import joinedload

from app.format06 import Format06
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.lib.statement_context import options_context
from app.lib.xmltodict import get_xattr
from app.limits import MAP_QUERY_AREA_MAX_SIZE, MAP_QUERY_LEGACY_NODES_LIMIT
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.models.db.user import User
from app.repositories.element_repository import ElementRepository

router = APIRouter(prefix='/api/0.6')


@router.get('/map')
@router.get('/map.xml')
@router.get('/map.json')
async def map_read(
    bbox: Annotated[str, Query()],
) -> dict:
    geometry = parse_bbox(bbox)
    if geometry.area > MAP_QUERY_AREA_MAX_SIZE:
        raise_for().map_query_area_too_big()

    at_sequence_id = await ElementRepository.get_current_sequence_id()

    with options_context(
        joinedload(Element.changeset)
        .load_only(Changeset.user_id)
        .joinedload(Changeset.user)
        .load_only(User.display_name)
    ):
        elements = await ElementRepository.find_many_by_query(
            geometry,
            at_sequence_id=at_sequence_id,
            nodes_limit=MAP_QUERY_LEGACY_NODES_LIMIT,
            legacy_nodes_limit=True,
        )

    xattr = get_xattr()
    minx, miny, maxx, maxy = geometry.bounds  # TODO: MultiPolygon support

    return {
        'bounds': {
            xattr('minlon'): minx,
            xattr('minlat'): miny,
            xattr('maxlon'): maxx,
            xattr('maxlat'): maxy,
        },
        **Format06.encode_elements(elements),
    }
