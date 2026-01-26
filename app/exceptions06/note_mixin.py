from datetime import datetime
from typing import override

from starlette import status

from app.config import NOTE_QUERY_AREA_MAX_SIZE
from app.exceptions.api_error import APIError
from app.exceptions.note_mixin import NoteExceptionsMixin
from app.lib.date_utils import legacy_date
from app.models.types import NoteId


class NoteExceptions06Mixin(NoteExceptionsMixin):
    @override
    def note_closed(self, note_id: NoteId, closed_at: datetime):
        raise APIError(
            status.HTTP_409_CONFLICT,
            detail=f'The note {note_id} was closed at {legacy_date(closed_at).isoformat()}',
        )

    @override
    def note_open(self, note_id: NoteId):
        raise APIError(
            status.HTTP_409_CONFLICT, detail=f'The note {note_id} is already open'
        )

    @override
    def notes_query_area_too_big(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {NOTE_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.',
        )
