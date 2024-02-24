from typing import NoReturn, override

from starlette import status

from app.exceptions.api_error import APIError
from app.exceptions.trace_mixin import TraceExceptionsMixin
from app.limits import TRACE_POINT_QUERY_AREA_MAX_SIZE


class TraceExceptions06Mixin(TraceExceptionsMixin):
    @override
    def trace_not_found(self, trace_id: int) -> NoReturn:
        raise APIError(status.HTTP_404_NOT_FOUND)

    @override
    def trace_access_denied(self, trace_id: int) -> NoReturn:
        raise APIError(status.HTTP_403_FORBIDDEN)

    @override
    def trace_points_query_area_too_big(self) -> NoReturn:
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            detail=f'The maximum bbox size is {TRACE_POINT_QUERY_AREA_MAX_SIZE}, and your request was too large. Please request a smaller area.',
        )

    @override
    def trace_file_unsupported_format(self, content_type: str) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail=f'Unsupported trace file format {content_type!r}')

    @override
    def trace_file_archive_too_deep(self) -> NoReturn:
        raise APIError(status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Trace file archive is too deep')

    @override
    def trace_file_archive_corrupted(self, content_type: str) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail=f'Trace file archive failed to decompress {content_type!r}')

    @override
    def trace_file_archive_too_many_files(self) -> NoReturn:
        raise APIError(status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Trace file archive contains too many files')

    @override
    def bad_trace_file(self, message: str) -> NoReturn:
        raise APIError(status.HTTP_400_BAD_REQUEST, detail=f'Failed to parse trace file: {message}')
