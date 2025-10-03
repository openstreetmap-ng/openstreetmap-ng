from abc import abstractmethod
from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError


class ImageExceptionsMixin:
    @abstractmethod
    def image_not_found(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def image_too_big(self) -> NoReturn:
        raise NotImplementedError

    def image_inappropriate(self) -> NoReturn:
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Image violates content policy',
        )
