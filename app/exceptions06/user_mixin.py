from typing import override

from starlette import status

from app.config import USER_PREF_BULK_SET_LIMIT
from app.exceptions.api_error import APIError
from app.exceptions.user_mixin import UserExceptionsMixin
from app.models.types import ApplicationId, DisplayName, UserId, UserPrefKey


class UserExceptions06Mixin(UserExceptionsMixin):
    @override
    def user_not_found(self, name_or_id: DisplayName | UserId):
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'User {name_or_id} not known')

    @override
    def user_not_found_bad_request(self, name_or_id: DisplayName | UserId):
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail=f'User {name_or_id} not known'
        )

    @override
    def pref_not_found(self, app_id: ApplicationId | None, key: UserPrefKey):
        raise APIError(
            status.HTTP_404_NOT_FOUND, detail=f'Preference {key!r} not found'
        )

    @override
    def pref_duplicate_key(self, key: UserPrefKey):
        raise APIError(
            status.HTTP_406_NOT_ACCEPTABLE,
            detail=f'Duplicate preferences with key {key}',
        )

    @override
    def pref_bulk_set_limit_exceeded(self):
        raise APIError(
            status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f'Too many preferences (limit is {USER_PREF_BULK_SET_LIMIT})',
        )
