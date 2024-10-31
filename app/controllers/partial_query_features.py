from base64 import urlsafe_b64encode
from collections.abc import Sequence
from typing import Annotated

import cython
from fastapi import APIRouter, Query
from shapely import Point

from app.format import FormatLeaflet
from app.lib.feature_icon import features_icons
from app.lib.feature_name import features_names
from app.lib.feature_prefix import features_prefixes
from app.lib.geo_utils import meters_to_degrees, meters_to_radians
from app.lib.render_response import render_response
from app.limits import QUERY_FEATURES_NODES_LIMIT
from app.models.db.element import Element
from app.models.geometry import Latitude, Longitude, Zoom
from app.models.proto.shared_pb2 import PartialQueryFeaturesParams
from app.queries.element_query import ElementQuery

router = APIRouter(prefix='/api/partial/query')


@router.get('/nearby')
async def query_nearby_features(
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    zoom: Annotated[Zoom, Query(ge=14)],
):
    radius = meters_to_degrees(10 * 1.5 ** (19 - zoom))  # match with app/static/js/index/_query-features.ts
    geom = Point(lon, lat).buffer(radius, quad_segs=3)  # 3x4=12 segments
    elements = await ElementQuery.find_many_by_geom(
        geom,
        nodes_limit=QUERY_FEATURES_NODES_LIMIT,
        resolve_all_members=True,
    )
    groups = FormatLeaflet.group_related_elements(elements)
    groups.sort(key=_nearby_sort_key)
    results: tuple[Element, ...] = tuple(group[0] for group in groups)
    icons = features_icons(results)
    names = features_names(results)
    prefixes = features_prefixes(results)
    renders = tuple(FormatLeaflet.encode_elements(group, detailed=True) for group in groups)

    params = PartialQueryFeaturesParams(renders=renders)
    return await render_response(
        'partial/query_features.jinja2',
        {
            'has_results': bool(results),
            'results': zip(results, icons, names, prefixes, strict=True),
            'params': urlsafe_b64encode(params.SerializeToString()).decode(),
        },
    )


@cython.cfunc
def _nearby_sort_key(group: Sequence[Element]):
    element = group[0]
    element_type = element.type
    if element_type == 'node':
        return (0, -element.id)
    elif element_type == 'way':
        return (1, -element.id)
    elif element_type == 'relation':
        return (2, -element.id)
    else:
        raise NotImplementedError(f'Unsupported element type {element_type!r}')
