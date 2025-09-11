from abc import abstractmethod
from typing import NoReturn

from fastapi import status

from app.exceptions.api_error import APIError
from app.models.types import TraceId


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

    def trace_file_unsupported_format(self, content_type: str) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Unsupported trace file format {content_type!r}',
        )

    @abstractmethod
    def trace_file_archive_too_deep(self) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_file_archive_corrupted(self, content_type: str) -> NoReturn:
        raise NotImplementedError

    @abstractmethod
    def trace_file_archive_too_many_files(self) -> NoReturn:
        raise NotImplementedError

    def bad_trace_file(self, message: str) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail=f'Invalid trace file: {message}'
        )
