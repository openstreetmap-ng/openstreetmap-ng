from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy.orm import joinedload

from app.format07 import Format07
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.lib.statement_context import options_context
from app.limits import MAP_QUERY_AREA_MAX_SIZE, MAP_QUERY_LEGACY_NODES_LIMIT
from app.models.db.changeset import Changeset
from app.models.db.element import Element
from app.repositories.element_repository import ElementRepository

router = APIRouter()


# TODO: limits
@router.get('/map')
async def get_map(
    bbox: Annotated[str, Query()],
):
    geometry = parse_bbox(bbox)
    if geometry.area > MAP_QUERY_AREA_MAX_SIZE:
        raise_for().map_query_area_too_big()

    with options_context(joinedload(Element.changeset).load_only(Changeset.user_id)):
        elements = await ElementRepository.find_many_by_query(
            geometry,
            nodes_limit=MAP_QUERY_LEGACY_NODES_LIMIT,
            legacy_nodes_limit=True,
        )

    return Format07.encode_elements(elements)
