from typing import override

from connectrpc.request import RequestContext
from shapely import Point, set_srid

from app.format import FormatRender
from app.lib.geo_utils import meters_to_degrees
from app.lib.query_features import QueryFeatures
from app.models.proto.query_features_connect import (
    Service,
    ServiceASGIApplication,
)
from app.models.proto.query_features_pb2 import NearbyRequest, NearbyResponse
from app.queries.element_spatial_query import ElementSpatialQuery
from speedup import split_typed_element_id


class _Service(Service):
    @override
    async def nearby(self, request: NearbyRequest, ctx: RequestContext):
        radius_meters = 10 * 1.5 ** (19 - request.at.zoom)
        origin = set_srid(Point(request.at.lon, request.at.lat), 4326)
        search_area = origin.buffer(meters_to_degrees(radius_meters), 4)

        spatial_elements = await ElementSpatialQuery.query_features(search_area)
        results = QueryFeatures.wrap_element_spatial(spatial_elements)
        renders = FormatRender.encode_query_features(results)

        response = NearbyResponse()
        for result, render in zip(results, renders):
            type, id = split_typed_element_id(result.element['typed_id'])
            response_result = response.results.add()
            response_result.type = type
            response_result.id = id
            response_result.prefix = result.prefix
            if result.display_name is not None:
                response_result.display_name = result.display_name
            if result.icon is not None:
                response_result.icon.icon = result.icon.filename
                response_result.icon.title = result.icon.title
            response_result.render.CopyFrom(render)

        return response


service = _Service()
asgi_app_cls = ServiceASGIApplication
