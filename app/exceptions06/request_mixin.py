from typing import NoReturn, override

from fastapi import status

from app.exceptions import APIError
from app.exceptions.request_mixin import RequestExceptionsMixin
from app.libc.naturalsize import naturalsize


class RequestExceptions06Mixin(RequestExceptionsMixin):
    @override
    def bad_geometry(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST)

    @override
    def bad_geometry_coordinates(self, lon: float, lat: float) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The latitudes must be between -90 and 90, longitudes between -180 and 180 and the minima must be less than the maxima.',
        )

    @override
    def bad_bbox(self, bbox: str, condition: str | None = None) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='The parameter bbox is required, and must be of the form min_lon,min_lat,max_lon,max_lat.',
        )

    @override
    def bad_xml(self, name: str, message: str, xml_input: str) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Cannot parse valid {name} from xml string {xml_input}. {message}',
        )

    @override
    def input_too_big(self, size: int) -> NoReturn:
        raise APIError(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'Request entity too large: {naturalsize(size)}',
        )
