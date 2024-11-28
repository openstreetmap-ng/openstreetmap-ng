import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response
from pydantic import PositiveInt

from app.format import FormatLeaflet
from app.lib.exceptions_context import raise_for
from app.lib.geo_utils import parse_bbox
from app.limits import MAP_QUERY_AREA_MAX_SIZE, MAP_QUERY_LEGACY_NODES_LIMIT
from app.models.proto.shared_pb2 import RenderElementsData
from app.queries.element_member_query import ElementMemberQuery
from app.queries.element_query import ElementQuery

router = APIRouter(prefix='/api/web')


@router.get('/map')
async def get_map(
    bbox: Annotated[str, Query()],
    limit: Annotated[PositiveInt | Literal[''], Query()],
):
    logging.warning('Limit is %r', limit)
    geometry = parse_bbox(bbox)
    if geometry.area > MAP_QUERY_AREA_MAX_SIZE:
        raise_for.map_query_area_too_big()

    if not limit:
        nodes_limit = MAP_QUERY_LEGACY_NODES_LIMIT
        legacy_nodes_limit = True
    else:
        nodes_limit = limit + 1
        legacy_nodes_limit = False

    elements = await ElementQuery.find_many_by_geom(
        geometry,
        partial_ways=True,
        include_relations=False,
        nodes_limit=nodes_limit,
        legacy_nodes_limit=legacy_nodes_limit,
    )

    if limit and len(elements) > limit:
        return Response(
            RenderElementsData(nodes=(), ways=(), too_much_data=True).SerializeToString(),
            media_type='application/x-protobuf',
        )

    await ElementMemberQuery.resolve_members(elements)
    return Response(
        FormatLeaflet.encode_elements(elements, detailed=True, areas=False).SerializeToString(),
        media_type='application/x-protobuf',
    )
