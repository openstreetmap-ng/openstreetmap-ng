from typing import override

from connectrpc.request import RequestContext
from shapely import Point, set_srid

from app.format import FormatRender
from app.lib.geo_utils import meters_to_degrees
from app.lib.query_features import QueryFeatures
from app.models.proto.query_features_connect import (
    QueryFeaturesService,
    QueryFeaturesServiceASGIApplication,
)
from app.models.proto.query_features_pb2 import NearbyRequest, NearbyResponse
from app.models.proto.shared_pb2 import ElementIcon
from app.queries.element_spatial_query import ElementSpatialQuery
from speedup import split_typed_element_id


class _Service(QueryFeaturesService):
    @override
    async def nearby(self, request: NearbyRequest, ctx: RequestContext):
        radius_meters = 10 * 1.5 ** (19 - request.at.zoom)
        origin = set_srid(Point(request.at.lon, request.at.lat), 4326)
        search_area = origin.buffer(meters_to_degrees(radius_meters), 4)

        spatial_elements = await ElementSpatialQuery.query_features(search_area)
        results = QueryFeatures.wrap_element_spatial(spatial_elements)
        renders = FormatRender.encode_query_features(results)

        response_results: list[NearbyResponse.Result] = []
        for result, render in zip(results, renders, strict=True):
            type, id = split_typed_element_id(result.element['typed_id'])
            icon = (
                ElementIcon(icon=result.icon.filename, title=result.icon.title)
                if result.icon is not None
                else None
            )
            response_results.append(
                NearbyResponse.Result(
                    type=type,
                    id=id,
                    prefix=result.prefix,
                    display_name=result.display_name,
                    icon=icon,
                    render=render,
                )
            )

        return NearbyResponse(results=response_results)


service = _Service()
asgi_app_cls = QueryFeaturesServiceASGIApplication
