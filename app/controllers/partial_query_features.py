from base64 import urlsafe_b64encode
from typing import Annotated

from fastapi import APIRouter, Query
from shapely import Point

from app.format import FormatRender
from app.lib.geo_utils import meters_to_degrees
from app.lib.query_features import QueryFeatures
from app.lib.render_response import render_response
from app.models.proto.shared_pb2 import PartialQueryFeaturesParams
from app.models.types import Latitude, Longitude, Zoom
from app.queries.element_spatial_query import ElementSpatialQuery
from app.validators.geometry import validate_geometry

router = APIRouter(prefix='/partial/query')


@router.get('/nearby')
async def query_nearby_features(
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    zoom: Annotated[Zoom, Query(ge=14)],
):
    radius_meters = 10 * 1.5 ** (
        19 - zoom
    )  # match with app/views/index/query-features.ts
    origin = validate_geometry(Point(lon, lat))
    search_area = origin.buffer(meters_to_degrees(radius_meters), 4)

    spatial_elements = await ElementSpatialQuery.query_features(search_area)
    results = QueryFeatures.wrap_element_spatial(spatial_elements)
    renders = FormatRender.encode_query_features(results, search_area=search_area)

    params = PartialQueryFeaturesParams(renders=renders)
    return await render_response(
        'partial/query-features',
        {
            'results': results,
            'params': urlsafe_b64encode(params.SerializeToString()).decode(),
        },
    )
