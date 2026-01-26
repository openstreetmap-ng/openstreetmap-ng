from typing import override

from starlette import status

from app.config import TRACE_POINT_QUERY_AREA_MAX_SIZE
from app.exceptions.api_error import APIError
from app.exceptions.trace_mixin import TraceExceptionsMixin
from app.models.types import TraceId


class TraceExceptions06Mixin(TraceExceptionsMixin):
    @override
    def trace_not_found(self, trace_id: TraceId):
        raise APIError(status.HTTP_404_NOT_FOUND)

    @override
    def trace_access_denied(self, trace_id: TraceId):
        raise APIError(status.HTTP_403_FORBIDDEN)

    @override
    def trace_points_query_area_too_big(self):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {TRACE_POINT_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.',
        )

    @override
    def trace_file_archive_too_deep(self):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Trace file archive is too deep',
        )

    @override
    def trace_file_archive_corrupted(self, content_type: str):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'Trace file archive failed to decompress {content_type!r}',
        )

    @override
    def trace_file_archive_too_many_files(self):
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Trace file archive contains too many files',
        )

    @override
    def bad_trace_file(self, message: str):
        raise APIError(
            status.HTTP_400_BAD_REQUEST, detail=f'Failed to parse trace file: {message}'
        )
