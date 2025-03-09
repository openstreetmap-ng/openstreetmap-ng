from abc import abstractmethod
from typing import NoReturn

from app.models.db.trace import TraceId


class TraceExceptionsMixin:
    @abstractmethod
    def trace_not_found(self, trace_id: TraceId) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_access_denied(self, trace_id: TraceId) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_points_query_area_too_big(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_file_unsupported_format(self, content_type: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_file_archive_too_deep(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_file_archive_corrupted(self, content_type: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_file_archive_too_many_files(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def bad_trace_file(self, message: str) -> NoReturn:
        raise NotImplementedError
