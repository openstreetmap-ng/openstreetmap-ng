from abc import abstractmethod
from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError


class MapExceptionsMixin:
    @abstractmethod
    def map_query_area_too_big(self) -> NoReturn:
        raise NotImplementedError

    def map_query_nodes_limit_exceeded(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail='Requested too much data',
        )
