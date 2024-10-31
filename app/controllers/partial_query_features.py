from base64 import urlsafe_b64encode
from typing import Annotated

from fastapi import APIRouter, Query
from shapely import Point

from app.format import FormatLeaflet
from app.lib.render_response import render_response
from app.models.geometry import Latitude, Longitude, Zoom
from app.models.proto.shared_pb2 import PartialQueryFeaturesParams
from app.queries.overpass_query import OverpassQuery

router = APIRouter(prefix='/api/partial/query')


@router.get('/nearby')
async def query_nearby_features(
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    zoom: Annotated[Zoom, Query(ge=14)],
):
    radius_meters = 10 * 1.5 ** (19 - zoom)  # match with app/static/js/index/_query-features.ts
    results = await OverpassQuery.nearby_elements(Point(lon, lat), radius_meters)
    renders = FormatLeaflet.encode_query_features(results)

    params = PartialQueryFeaturesParams(renders=renders)
    return await render_response(
        'partial/query_features.jinja2',
        {
            'results': results,
            'params': urlsafe_b64encode(params.SerializeToString()).decode(),
        },
    )
