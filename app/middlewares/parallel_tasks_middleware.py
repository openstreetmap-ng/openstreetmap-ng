from asyncio import Task, TaskGroup
from contextlib import contextmanager
from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Send
from starlette.types import Scope as StarletteScope

from app.lib.auth_context import auth_scopes
from app.middlewares.request_context_middleware import get_request
from app.queries.message_query import MessageQuery

_MESSAGES_COUNT_UNREAD_CTX: ContextVar[Task[int]] = ContextVar('MessageCountUnread')


@contextmanager
def _messages_count_unread(tg: TaskGroup):
    # skip count_unread for API and static requests
    if 'web_user' not in auth_scopes() or get_request().url.path.startswith(('/api/', '/static')):
        yield
        return

    task = tg.create_task(MessageQuery.count_unread())
    token = _MESSAGES_COUNT_UNREAD_CTX.set(task)
    try:
        yield
    finally:
        _MESSAGES_COUNT_UNREAD_CTX.reset(token)


class ParallelTasksMiddleware:
    """Perform tasks during request processing."""

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: StarletteScope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        async with TaskGroup() as tg:
            with _messages_count_unread(tg):
                await self.app(scope, receive, send)

    @staticmethod
    async def messages_count_unread() -> int | None:
        """Get the number of unread messages."""
        task = _MESSAGES_COUNT_UNREAD_CTX.get(None)
        return (await task) if (task is not None) else None
