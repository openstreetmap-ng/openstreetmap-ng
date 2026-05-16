import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import timedelta
from functools import wraps
from random import uniform
from time import monotonic
from typing import Any, ParamSpec, TypeVar

import cython
from sentry_sdk import capture_exception

_P = ParamSpec('_P')
_R = TypeVar('_R')


def retry(
    timeout: timedelta | None,
    *,
    sleep_init: cython.double = 0.15,
    sleep_limit: cython.double = 300,
):
    """Decorator to retry a function until it succeeds or the timeout is reached."""
    timeout_seconds: cython.double = 0 if timeout is None else timeout.total_seconds()

    def decorator(func: Callable[_P, Coroutine[Any, Any, _R]]):
        @wraps(func)
        async def wrapper(*args: _P.args, **kwargs: _P.kwargs):
            ts: cython.double = monotonic()
            sleep: cython.double = sleep_init
            attempt: cython.size_t = 0

            while True:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    capture_exception()
                    attempt += 1

                    # retry is not possible, re-raise the exception
                    now: cython.double = monotonic()
                    next_timeout_seconds: cython.double = now + sleep - ts
                    if next_timeout_seconds >= timeout_seconds and timeout is not None:
                        raise TimeoutError(
                            f'{func.__qualname__} failed and timed out after {attempt} attempts'
                        ) from e

                    # retry is still possible
                    logging.info(
                        '%s failed (attempt %d), retrying in %.3fs',
                        func.__qualname__,
                        attempt,
                        sleep,
                        exc_info=True,
                    )
                    await asyncio.sleep(sleep)
                    sleep = uniform(sleep * 1.5, sleep * 2.5)
                    sleep = min(sleep, sleep_limit)

        return wrapper

    return decorator
