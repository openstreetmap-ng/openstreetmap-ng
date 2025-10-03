from typing import NoReturn, override

from starlette import status

from app.exceptions.api_error import APIError
from app.exceptions.image_mixin import ImageExceptionsMixin


class ImageExceptions06Mixin(ImageExceptionsMixin):
    @override
    def image_not_found(self) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail='Image not found')

    @override
    def image_too_big(self) -> NoReturn:
        raise APIError(status.HTTP_422_UNPROCESSABLE_CONTENT, detail='Image is too big')
