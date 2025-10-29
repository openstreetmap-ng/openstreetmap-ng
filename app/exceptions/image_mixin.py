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

    def bad_image_format(self) -> NoReturn:
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Invalid image format or corrupted image',
        )

    def image_proxy_not_found(self, proxy_id: int) -> NoReturn:
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'Image proxy {proxy_id} not found',
        )

    def image_proxy_fetch_failed(self, url: str) -> NoReturn:
        raise APIError(
            status.HTTP_502_BAD_GATEWAY,
            detail=f'Failed to fetch image from {url}',
        )
