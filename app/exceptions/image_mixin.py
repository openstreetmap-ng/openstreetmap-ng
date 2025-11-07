from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError


class ImageExceptionsMixin:
    def image_not_found(self) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Image not found')

    def image_too_big(self) -> NoReturn:
        raise APIError(status.HTTP_422_UNPROCESSABLE_CONTENT, detail='Image is too big')

    def image_inappropriate(self) -> NoReturn:
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Image violates content policy',
        )
