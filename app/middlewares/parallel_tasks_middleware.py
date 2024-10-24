from asyncio import Task, TaskGroup
from contextlib import contextmanager
from contextvars import ContextVar

from starlette.types import ASGIApp, Receive, Scope, Send

from app.lib.auth_context import auth_user
from app.middlewares.request_context_middleware import get_request
from app.queries.message_query import MessageQuery

_messages_count_unread_context: ContextVar[Task[int]] = ContextVar('_messages_count_unread_context')


@contextmanager
def _messages_count_unread(tg: TaskGroup):
    if auth_user() is None or get_request().url.path.startswith(('/api/', '/oauth2/', '/static')):
        yield
        return

    token = _messages_count_unread_context.set(tg.create_task(MessageQuery.count_unread()))
    try:
        yield
    finally:
        _messages_count_unread_context.reset(token)


class ParallelTasksMiddleware:
    """
    Perform tasks during request processing.
    """

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        async with TaskGroup() as tg:
            with _messages_count_unread(tg):
                await self.app(scope, receive, send)

    @staticmethod
    async def messages_count_unread() -> int:
        """
        Get the number of unread messages.
        """
        return await _messages_count_unread_context.get()
