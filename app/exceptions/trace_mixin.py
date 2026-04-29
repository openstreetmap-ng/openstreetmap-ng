from fastapi import status

from app.config import TRACE_POINT_QUERY_AREA_MAX_SIZE
from app.exceptions.api_error import APIError
from app.models.types import TraceId


class TraceExceptionsMixin:
    def trace_not_found(self, trace_id: TraceId):
        raise APIError(
            status.HTTP_404_NOT_FOUND,
            detail='Trace not found',
        )

    def trace_access_denied(self, trace_id: TraceId):
        raise APIError(
            status.HTTP_403_FORBIDDEN,
            detail='Trace access denied',
        )

    def trace_points_query_area_too_big(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Trace query area is too large (maximum {TRACE_POINT_QUERY_AREA_MAX_SIZE})',
        )

    def trace_file_unsupported_format(self, content_type: str):
        raise APIError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f'Trace file format is not supported: {content_type!r}',
        )

    def trace_file_archive_too_deep(self):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Trace file archive is too deep',
        )

    def trace_file_archive_corrupted(self, content_type: str):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'Trace file archive is corrupted: {content_type!r}',
        )

    def trace_file_archive_too_many_files(self):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Trace file archive contains too many files',
        )

    def bad_trace_file(self, message: str):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f'Trace file is invalid: {message}',
        )
