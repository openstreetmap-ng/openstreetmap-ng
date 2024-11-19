from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError


class DiaryExceptionsMixin:
    def diary_not_found(self, id: int) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'Diary {id} not found')
