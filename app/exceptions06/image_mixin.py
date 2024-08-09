from typing import TYPE_CHECKING, NoReturn, override

from starlette import status

from app.exceptions.api_error import APIError
from app.exceptions.image_mixin import ImageExceptionsMixin

if TYPE_CHECKING:
    from app.lib.storage.base import StorageKey


class ImageExceptions06Mixin(ImageExceptionsMixin):
    @override
    def image_not_found(self, file_id: 'StorageKey') -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'Avatar {file_id!r} not found')

    @override
    def image_too_big(self) -> NoReturn:
        raise APIError(status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Image is too big')
