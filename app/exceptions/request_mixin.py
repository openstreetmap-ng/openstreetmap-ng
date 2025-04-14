from abc import abstractmethod
from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError


class RequestExceptionsMixin:
    def request_timeout(self) -> NoReturn:
        raise APIError(status.HTTP_504_GATEWAY_TIMEOUT, detail='Request Timeout')

    def too_many_requests(self) -> NoReturn:
        raise APIError(status.HTTP_429_TOO_MANY_REQUESTS, detail='Too Many Requests')

    def bad_cursor(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='Invalid database cursor')

    def cursor_expired(self) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail='Database cursor expired')

    @abstractmethod
    def bad_geometry(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def bad_geometry_coordinates(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def bad_bbox(self, bbox: str, condition: str | None = None) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def bad_xml(
        self, name: str, message: str, xml_input: bytes | None = None
    ) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def input_too_big(self, size: int) -> NoReturn:
        raise NotImplementedError
