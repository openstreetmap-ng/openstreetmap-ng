from abc import abstractmethod
from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError
from app.models.types import ApplicationId, DisplayName, UserId, UserPrefKey


class UserExceptionsMixin:
    def user_not_found(self, name_or_id: DisplayName | UserId) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'User {name_or_id} not found')

    @abstractmethod
    def user_not_found_bad_request(self, name_or_id: DisplayName | UserId) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def pref_not_found(self, app_id: ApplicationId | None, key: UserPrefKey) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def pref_duplicate_key(self, key: UserPrefKey) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def pref_bulk_set_limit_exceeded(self) -> NoReturn:
        raise NotImplementedError
