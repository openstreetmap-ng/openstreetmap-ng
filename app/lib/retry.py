import asyncio
import logging
import random
import time
from datetime import timedelta
from functools import wraps

import cython


def retry(timeout: timedelta | None, *, sleep_init: cython.double = 0.15, sleep_limit: cython.double = 300):
    """
    Decorator to retry a function until it succeeds or the timeout is reached.
    """
    timeout_seconds: cython.double = 0 if timeout is None else timeout.total_seconds()

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ts: cython.double = time.monotonic()
            sleep: cython.double = sleep_init
            attempt: cython.int = 0

            while True:
                attempt += 1

                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # retry is not possible, re-raise the exception
                    now: cython.double = time.monotonic()
                    next_timeout_seconds: cython.double = now + sleep - ts
                    if next_timeout_seconds >= timeout_seconds and timeout is not None:
                        raise TimeoutError(f'{func.__qualname__} failed and timed out after {attempt} attempts') from e
                    # retry is still possible
                    logging.info(
                        '%s failed (attempt %d), retrying in %.3f sec',
                        func.__qualname__,
                        attempt,
                        sleep,
                        exc_info=True,
                    )
                    await asyncio.sleep(sleep)
                    sleep = min(random.uniform(sleep * 1.5, sleep * 2.5), sleep_limit)  # noqa: S311

        return wrapper

    return decorator
