from typing import Annotated

from anyio import create_task_group
from fastapi import APIRouter, Query

from app.format07 import Format07
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.limits import MAP_QUERY_AREA_MAX_SIZE, MAP_QUERY_LEGACY_NODES_LIMIT
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery
from app.queries.user_query import UserQuery

router = APIRouter(prefix='/api/0.7')


# TODO: limits + cursor (1min expiration?)
@router.get('/map')
async def get_map(bbox: Annotated[str, Query()]):
    geometry = parse_bbox(bbox)
    if geometry.area > MAP_QUERY_AREA_MAX_SIZE:
        raise_for().map_query_area_too_big()

    elements = await ElementQuery.find_many_by_geom(
        geometry,
        nodes_limit=MAP_QUERY_LEGACY_NODES_LIMIT,
        legacy_nodes_limit=True,
    )

    async with create_task_group() as tg:
        tg.start_soon(UserQuery.resolve_elements_users, elements, False)
        tg.start_soon(ElementMemberQuery.resolve_members, elements)

    return Format07.encode_elements(elements)
