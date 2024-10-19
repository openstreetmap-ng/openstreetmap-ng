from abc import abstractmethod
from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError


class UserExceptionsMixin:
    def user_not_found(self, name_or_id: str | int) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'User {name_or_id} not found')

    @abstractmethod
    def user_not_found_bad_request(self, name_or_id: str | int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def pref_not_found(self, app_id: int | None, key: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def pref_duplicate_key(self, key: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def pref_bulk_set_limit_exceeded(self) -> NoReturn:
        raise NotImplementedError
