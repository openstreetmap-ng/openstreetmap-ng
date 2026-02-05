import importlib
import logging
from collections.abc import Awaitable, Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, cast, override

import cython
from connectrpc.code import Code
from connectrpc.errors import ConnectError
from connectrpc.interceptor import UnaryInterceptor
from connectrpc.request import REQ, RES, RequestContext
from protovalidate import collect_violations
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.routing import Route

from app.config import REQUEST_BODY_MAX_SIZE
from app.lib.standard_feedback import MessageSeverity
from app.models.proto.query_features_connect import QueryFeaturesServiceASGIApplication
from app.models.proto.shared_pb2 import StandardFeedbackDetail
from buf.validate import validate_pb2

_HTTP_STATUS_CODE_TO_CONNECT_CODE = {
    400: Code.INVALID_ARGUMENT,
    401: Code.UNAUTHENTICATED,
    403: Code.PERMISSION_DENIED,
    404: Code.NOT_FOUND,
    408: Code.DEADLINE_EXCEEDED,
    409: Code.ABORTED,
    412: Code.FAILED_PRECONDITION,
    413: Code.RESOURCE_EXHAUSTED,
    415: Code.INVALID_ARGUMENT,
    422: Code.INVALID_ARGUMENT,
    429: Code.RESOURCE_EXHAUSTED,
    451: Code.PERMISSION_DENIED,
    500: Code.INTERNAL,
    501: Code.UNIMPLEMENTED,
    502: Code.UNAVAILABLE,
    503: Code.UNAVAILABLE,
    504: Code.DEADLINE_EXCEEDED,
}


@cython.cfunc
def _standard_feedback_detail(detail: Any):
    if isinstance(detail, dict):
        detail = detail.get('detail')
    if not detail or not isinstance(detail, (list, tuple)):
        return None

    entries: list[StandardFeedbackDetail.Entry] = []
    for item in detail:
        if not isinstance(item, dict):
            continue

        type: MessageSeverity | None = item.get('type')
        loc: Sequence[str] | None = item.get('loc')
        msg: str | None = item.get('msg')
        if type is None or loc is None or msg is None:
            continue

        entries.append(
            StandardFeedbackDetail.Entry(
                severity=type,
                field=loc[1] if len(loc) >= 2 else None,
                message=msg,
            )
        )

    return StandardFeedbackDetail(entries=entries) if entries else None


@cython.cfunc
def _http_exception_to_connect_error(exc: HTTPException):
    code = _HTTP_STATUS_CODE_TO_CONNECT_CODE.get(exc.status_code, Code.UNKNOWN)
    detail = cast('Any', exc.detail)

    if isinstance(detail, str):
        return ConnectError(code, detail)

    feedback = _standard_feedback_detail(detail)
    if feedback is not None:
        message = next(
            (
                e.message
                for e in feedback.entries
                if e.severity == StandardFeedbackDetail.Severity.error
            ),
            feedback.entries[0].message,
        )
        return ConnectError(code, message, details=(feedback,))

    return ConnectError(code, str(detail))


@cython.cfunc
def _protovalidate_to_standard_feedback(
    violations: Iterable[validate_pb2.Violation],
):
    return StandardFeedbackDetail(
        entries=[
            StandardFeedbackDetail.Entry(
                severity='error',
                message=violation.message,
                field=(
                    '.'.join(element.field_name for element in violation.field.elements)
                    or None
                ),
            )
            for violation in violations
        ]
    )


class _ValidateInterceptor(UnaryInterceptor):
    @override
    async def intercept_unary(
        self,
        call_next: Callable[[REQ, RequestContext], Awaitable[RES]],
        request: REQ,
        ctx: RequestContext,
    ):
        violations = collect_violations(request)  # type: ignore
        if violations:
            feedback = _protovalidate_to_standard_feedback(v.proto for v in violations)
            raise ConnectError(
                Code.INVALID_ARGUMENT,
                feedback.entries[0].message,
                details=(feedback,),
            )

        try:
            return await call_next(request, ctx)
        except HTTPException as exc:
            raise _http_exception_to_connect_error(exc) from exc


interceptors = (_ValidateInterceptor(),)
routes: list[Route] = []

for p in sorted(Path('app/rpc').glob('*.py')):
    if p.name == 'app.py':
        continue

    module_name = p.as_posix().replace('/', '.')[:-3]
    module = importlib.import_module(module_name)
    service = module.service
    asgi_app_cls: type[QueryFeaturesServiceASGIApplication] = module.asgi_app_cls
    asgi_app = asgi_app_cls(
        service=service,
        interceptors=interceptors,
        read_max_bytes=REQUEST_BODY_MAX_SIZE,
    )
    routes.append(Route(f'{asgi_app.path}/{{path:path}}', asgi_app))

logging.info('Loaded %d RPC services', len(routes))
app = Starlette(routes=routes)
del interceptors, routes
