import logging
from asyncio import TaskGroup
from functools import wraps

from fastapi import HTTPException
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import RATE_LIMIT_OPTIMISTIC_BLACKLIST_EXPIRE
from app.lib.auth_context import auth_user
from app.lib.file_cache import FileCache
from app.lib.user_role_limits import UserRoleLimits
from app.middlewares.request_context_middleware import get_request
from app.models.types import StorageKey
from app.services.rate_limit_service import RateLimitService

_BLACKLIST = FileCache('RateLimit')


class RateLimitMiddleware:
    """
    Rate limiting middleware.

    The endpoint must be decorated with @rate_limit to enable rate limiting.
    """

    __slots__ = ('app',)

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        async def wrapper(message: Message) -> None:
            if message['type'] == 'http.response.start':
                state = get_request().state._state  # noqa: SLF001
                rate_limit_headers: dict | None = state.get('rate_limit_headers')
                if rate_limit_headers is not None:
                    headers = MutableHeaders(raw=message['headers'])
                    headers.update(rate_limit_headers)

            return await send(message)

        return await self.app(scope, receive, wrapper)


def rate_limit(*, weight: float = 1):
    """
    Decorator to rate limit an endpoint. The rate limit quota is global.
    The weight can be increased in runtime using the set_rate_limit_weight method.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            req = get_request()
            user = auth_user()
            if user is not None:
                key: StorageKey = f'id:{user["id"]}'  # type: ignore
                quota = UserRoleLimits.get_rate_limit_quota(user['roles'])
            else:
                key: StorageKey = f'ip:{req.client.host}'  # type: ignore
                quota = UserRoleLimits.get_rate_limit_quota(None)

            if await _BLACKLIST.get(key) is None:
                # If not blacklisted, perform optimistic checking to reduce latency.
                async with TaskGroup() as tg:
                    request_task = tg.create_task(func(*args, **kwargs))

                    try:
                        rate_limit_headers = await RateLimitService.update(
                            key, weight, quota
                        )
                    except HTTPException:
                        # If rate limit is hit, temporarily blacklist the user from optimistic checks.
                        request_task.cancel()
                        async with _BLACKLIST.lock(key) as lock:
                            if await _BLACKLIST.get(key) is None:
                                logging.info(
                                    'Rate limit hit for %r, '
                                    'blacklisting from optimistic checks',
                                    key,
                                )
                                await _BLACKLIST.set(
                                    lock,
                                    b'',
                                    ttl=RATE_LIMIT_OPTIMISTIC_BLACKLIST_EXPIRE,
                                )
                        raise

                result = request_task.result()

            else:
                # If blacklisted, perform sequential checking to save on resources.
                rate_limit_headers = await RateLimitService.update(key, weight, quota)
                result = await func(*args, **kwargs)

            # Check if the weight was increased
            state = req.state._state  # noqa: SLF001
            weight_change: float = state.get('rate_limit_weight', weight) - weight
            if weight_change > 0:
                rate_limit_headers = await RateLimitService.update(
                    key, weight_change, quota, raise_on_limit=None
                )

            # Save the headers to the request state
            state['rate_limit_headers'] = rate_limit_headers
            return result

        return wrapper

    return decorator


def set_rate_limit_weight(weight: float) -> None:
    """Increase the request weight for rate limiting. Decreasing weights are ignored."""
    logging.debug('Overriding rate limit weight to %s', weight)
    state = get_request().state._state  # noqa: SLF001
    state['rate_limit_weight'] = weight
