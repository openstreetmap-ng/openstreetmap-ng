from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError
from app.models.types import DiaryCommentId, DiaryId


class DiaryExceptionsMixin:
    def diary_not_found(self, id: DiaryId) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'Diary {id} not found')

    def diary_comment_not_found(self, id: DiaryCommentId) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND, detail=f'Diary comment {id} not found')
