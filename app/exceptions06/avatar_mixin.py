from typing import NoReturn, override

from starlette import status

from app.exceptions.api_error import APIError
from app.exceptions.avatar_mixin import AvatarExceptionsMixin


class AvatarExceptions06Mixin(AvatarExceptionsMixin):
    @override
    def avatar_not_found(self, avatar_id: str) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'Avatar {avatar_id!r} not found')

    @override
    def avatar_too_big(self) -> NoReturn:
        raise APIError(status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Avatar is too big')
