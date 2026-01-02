from typing import Annotated

from fastapi import APIRouter, Query, Response
from shapely import Point

from app.format import FormatRender
from app.lib.geo_utils import meters_to_degrees
from app.lib.query_features import QueryFeatures
from app.models.proto.shared_pb2 import ElementIcon, QueryFeaturesNearbyData
from app.models.types import Latitude, Longitude, Zoom
from app.queries.element_spatial_query import ElementSpatialQuery
from app.validators.geometry import validate_geometry
from speedup import split_typed_element_id

router = APIRouter(prefix='/api/web/query-features')


@router.get('/nearby')
async def query_nearby_features(
    lon: Annotated[Longitude, Query()],
    lat: Annotated[Latitude, Query()],
    zoom: Annotated[Zoom, Query(ge=14)],
):
    radius_meters = 10 * 1.5 ** (
        19 - zoom
    )  # match with app/views/index/query-features.tsx
    origin = validate_geometry(Point(lon, lat))
    search_area = origin.buffer(meters_to_degrees(radius_meters), 4)

    spatial_elements = await ElementSpatialQuery.query_features(search_area)
    results = QueryFeatures.wrap_element_spatial(spatial_elements)
    renders = FormatRender.encode_query_features(results)

    response_results: list[QueryFeaturesNearbyData.Result] = []
    for result, render in zip(results, renders, strict=True):
        type, id = split_typed_element_id(result.element['typed_id'])
        icon = (
            ElementIcon(icon=result.icon.filename, title=result.icon.title)
            if result.icon is not None
            else None
        )
        response_results.append(
            QueryFeaturesNearbyData.Result(
                type=type,
                id=id,
                prefix=result.prefix,
                display_name=result.display_name,
                icon=icon,
                render=render,
            )
        )

    return Response(
        QueryFeaturesNearbyData(results=response_results).SerializeToString(),
        media_type='application/x-protobuf',
    )
