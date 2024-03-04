import logging
import random
import time
from datetime import timedelta
from functools import wraps

import anyio
import cython


def retry(timeout: timedelta | None, *, sleep_init: float = 0.15, sleep_limit: float = 300):
    """
    Decorator to retry a function.

    The function is retried until it succeeds or the timeout is reached.
    """

    timeout_seconds: cython.double = -1 if timeout is None else timeout.total_seconds()

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
                    now: cython.double = time.monotonic()
                    next_timeout_seconds: cython.double = now + sleep - ts

                    # retry is still possible
                    if next_timeout_seconds < timeout_seconds or timeout_seconds < 0:
                        logging.info(
                            '%s failed (attempt %d), retrying in %.3f sec',
                            func.__qualname__,
                            attempt,
                            sleep,
                            exc_info=True,
                        )

                        await anyio.sleep(sleep)
                        noise: cython.double = random.random()  # noqa: S311
                        new_sleep: cython.double = sleep * (1.5 + noise)
                        sleep = new_sleep if new_sleep < sleep_limit else sleep_limit

                    # retry is not possible, re-raise the exception
                    raise TimeoutError(f'{func.__qualname__} failed and timed out after {attempt} attempts') from e

        return wrapper

    return decorator
