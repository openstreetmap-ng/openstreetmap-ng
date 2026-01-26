from abc import abstractmethod
from datetime import datetime
from typing import NoReturn

from starlette import status

from app.exceptions.api_error import APIError
from app.models.types import NoteId


class NoteExceptionsMixin:
    def note_not_found(self, note_id: NoteId):
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail=f'note/{note_id} not found',
        )

    @abstractmethod
    def note_closed(self, note_id: NoteId, closed_at: datetime) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def note_open(self, note_id: NoteId) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def notes_query_area_too_big(self) -> NoReturn:
        raise NotImplementedError
