from datetime import datetime
from typing import NoReturn, override

from starlette import status

from app.exceptions.api_error import APIError
from app.exceptions.note_mixin import NoteExceptionsMixin
from app.lib.date_utils import format_iso_date
from app.limits import NOTE_QUERY_AREA_MAX_SIZE


class NoteExceptions06Mixin(NoteExceptionsMixin):
    @override
    def note_not_found(self, note_id: int) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND)

    @override
    def note_closed(self, note_id: int, closed_at: datetime) -> NoReturn:
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The note {note_id} was closed at {format_iso_date(closed_at)}',
        )

    @override
    def note_open(self, note_id: int) -> NoReturn:
        raise APIError(status.HTTP_409_CONFLICT, detail=f'The note {note_id} is already open')

    @override
    def notes_query_area_too_big(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {NOTE_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.',
        )
