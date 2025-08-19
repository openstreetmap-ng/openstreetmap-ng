from asyncio import Task, TaskGroup
from contextlib import contextmanager
from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Send
from starlette.types import Scope as StarletteScope

from app.lib.auth_context import auth_scopes, auth_user
from app.middlewares.request_context_middleware import get_request
from app.models.db.user import user_is_admin, user_is_moderator
from app.queries.message_query import MessageQuery
from app.queries.report_query import ReportQuery, _ReportCountResult

_MESSAGES_COUNT_UNREAD_CTX = ContextVar[Task[int]]('MessageCountUnread')
_REPORTS_COUNT_ATTENTION_CTX = ContextVar[Task[_ReportCountResult]](
    'ReportsCountAttention'
)


@contextmanager
def _messages_count_unread(tg: TaskGroup):
    # skip count_unread for API and static requests
    if (
        'web_user' not in auth_scopes()  #
        or get_request().url.path.startswith((
            '/api/',
            '/static',
        ))
    ):
        yield
        return

    task = tg.create_task(MessageQuery.count_unread())
    token = _MESSAGES_COUNT_UNREAD_CTX.set(task)
    try:
        yield
    finally:
        _MESSAGES_COUNT_UNREAD_CTX.reset(token)


@contextmanager
def _reports_count_attention(tg: TaskGroup):
    # Only count reports for moderators and admins
    user = auth_user()
    if user is None or not user_is_moderator(user):
        yield
        return

    # Skip for API and static requests
    if get_request().url.path.startswith((
        '/api/',
        '/static',
    )):
        yield
        return

    # Determine visibility level based on user role
    visible_to = 'administrator' if user_is_admin(user) else 'moderator'
    task = tg.create_task(ReportQuery.count_requiring_attention(visible_to))
    token = _REPORTS_COUNT_ATTENTION_CTX.set(task)
    try:
        yield
    finally:
        _REPORTS_COUNT_ATTENTION_CTX.reset(token)


class ParallelTasksMiddleware:
    """Perform tasks during request processing."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: StarletteScope, receive: Receive, send: Send
    ) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async with TaskGroup() as tg:
            with _messages_count_unread(tg), _reports_count_attention(tg):
                try:
                    return await self.app(scope, receive, send)
                except Exception as e:
                    for t in tg._tasks:  # noqa: SLF001
                        t.cancel()
                    exception = e

        # Propagate app exception unaltered
        raise exception

    @staticmethod
    async def messages_count_unread() -> int | None:
        """Get the number of unread messages."""
        task = _MESSAGES_COUNT_UNREAD_CTX.get(None)
        return (await task) if task is not None else None

    @staticmethod
    async def reports_count_attention() -> _ReportCountResult | None:
        """Get the number of reports requiring attention."""
        task = _REPORTS_COUNT_ATTENTION_CTX.get(None)
        return (await task) if task is not None else None
