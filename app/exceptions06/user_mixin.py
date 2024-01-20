from typing import NoReturn, override

from fastapi import status

from app.exceptions.api_error import APIError
from app.exceptions.user_mixin import UserExceptionsMixin
from app.limits import USER_PREF_BULK_SET_LIMIT


class UserExceptions06Mixin(UserExceptionsMixin):
    @override
    def user_not_found(self, name_or_id: str | int) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'User {name_or_id} not known')

    @override
    def user_not_found_bad_request(self, name_or_id: str | int) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail=f'User {name_or_id} not known')

    @override
    def pref_not_found(self, app_id: int | None, key: str) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'Preference {key!r} not found')

    @override
    def pref_duplicate_key(self, key: str) -> NoReturn:
        raise APIError(status.HTTP_406_NOT_ACCEPTABLE, detail=f'Duplicate preferences with key {key}')

    @override
    def pref_bulk_set_limit_exceeded(self) -> NoReturn:
        raise APIError(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f'Too many preferences (limit is {USER_PREF_BULK_SET_LIMIT})',
        )
