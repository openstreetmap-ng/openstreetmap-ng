from abc import abstractmethod
from datetime import datetime
from typing import NoReturn


class NoteExceptionsMixin:
    @abstractmethod
    def note_not_found(self, note_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def note_closed(self, note_id: int, closed_at: datetime) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def note_open(self, note_id: int) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def notes_query_area_too_big(self) -> NoReturn:
        raise NotImplementedError
