from typing import override

from starlette import status

from app.config import MAP_QUERY_AREA_MAX_SIZE, MAP_QUERY_LEGACY_NODES_LIMIT
from app.exceptions.api_error import APIError
from app.exceptions.map_mixin import MapExceptionsMixin


class MapExceptions06Mixin(MapExceptionsMixin):
    @override
    def map_query_area_too_big(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {MAP_QUERY_AREA_MAX_SIZE}, and your request was too large. Either request a smaller area, or use planet.osm',
        )

    @override
    def map_query_nodes_limit_exceeded(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'You requested too many nodes (limit is {MAP_QUERY_LEGACY_NODES_LIMIT}). Either request a smaller area, or use planet.osm',
        )
