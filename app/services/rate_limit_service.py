import asyncio
import logging
import random
from asyncio import Event, TaskGroup
from contextlib import asynccontextmanager
from datetime import timedelta
from time import perf_counter

from fastapi import HTTPException
from psycopg import AsyncConnection
from sentry_sdk import start_transaction
from starlette import status

from app.config import SENTRY_RATE_LIMIT_MANAGEMENT_MONITOR, TEST_ENV
from app.db import db
from app.lib.retry import retry
from app.lib.testmethod import testmethod

_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()

_QUOTA_WINDOW = timedelta(hours=1)
_QUOTA_WINDOW_SECONDS = _QUOTA_WINDOW.total_seconds()


class RateLimitService:
    @staticmethod
    async def update(
        key: str,
        change: float,
        quota: float,
        *,
        raise_on_limit: bool = True,
    ) -> dict[str, str]:
        """
        Update the rate limit counter and check if the limit is exceeded.
        Returns the response headers or raises a HTTPException.
        """
        quota_per_second = quota / _QUOTA_WINDOW_SECONDS

        async with db(True) as conn:
            # Uses a leaky bucket algorithm where the usage decreases over time.
            async with await conn.execute(
                """
                INSERT INTO rate_limit (
                    key, usage
                )
                VALUES (
                    %(key)s, %(change)s
                )
                ON CONFLICT (key) DO UPDATE SET
                    usage = GREATEST(
                        rate_limit.usage -
                        EXTRACT(EPOCH FROM (statement_timestamp() - updated_at)) * %(quota_per_second)s,
                        0
                    ) + EXCLUDED.usage,
                    updated_at = DEFAULT
                RETURNING usage
                """,
                {
                    'key': key,
                    'change': change,
                    'quota_per_second': quota_per_second,
                },
            ) as r:
                usage: float = (await r.fetchone())[0]  # type: ignore

            # Prepare headers
            quota_remaining = max(quota - usage, 0)
            reset_seconds = usage / quota_per_second
            headers = {
                'RateLimit': f'"default";r={quota_remaining:.0f};t={reset_seconds:.0f}',
                'RateLimit-Policy': f'"default";q={quota:.0f};w={_QUOTA_WINDOW_SECONDS:.0f}',
            }

            # Check if the limit is exceeded
            if usage > quota and raise_on_limit:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail='Rate limit exceeded',
                    headers=headers,
                )

            return headers

    @staticmethod
    @asynccontextmanager
    async def context():
        """Context manager for deleting expired rate limit entries."""
        async with TaskGroup() as tg:
            task = tg.create_task(_process_task())
            yield
            task.cancel()

    @staticmethod
    @testmethod
    async def force_process():
        """
        Force the rate limit processing loop to wake up early, and wait for it to finish.
        This method is only available during testing, and is limited to the current process.
        """
        logging.debug('Requesting rate limit processing loop early wakeup')
        _PROCESS_REQUEST_EVENT.set()
        _PROCESS_DONE_EVENT.clear()
        await _PROCESS_DONE_EVENT.wait()


@retry(None)
async def _process_task() -> None:
    while True:
        async with db(True) as conn:
            # Lock is just a random unique number
            async with await conn.execute('SELECT pg_try_advisory_xact_lock(8569304793767999080::bigint)') as r:
                acquired: bool = (await r.fetchone())[0]  # type: ignore

            if acquired:
                ts = perf_counter()
                with SENTRY_RATE_LIMIT_MANAGEMENT_MONITOR, start_transaction(op='task', name='rate-limit-management'):
                    await _delete_expired(conn)
                tt = perf_counter() - ts

                # on success, sleep ~5min
                delay = random.uniform(290, 310) - tt  # noqa: S311
            else:
                # on failure, sleep ~1h
                delay = random.uniform(1800, 5400)  # noqa: S311

        if not TEST_ENV:
            await asyncio.sleep(delay)
            continue

        # Test environment supports early wakeup
        _PROCESS_DONE_EVENT.set()
        async with TaskGroup() as tg:
            event_task = tg.create_task(_PROCESS_REQUEST_EVENT.wait())
            await asyncio.wait((event_task,), timeout=delay)
            if event_task.done():
                logging.debug('Rate limit processing loop early wakeup')
                _PROCESS_REQUEST_EVENT.clear()
            else:
                event_task.cancel()


async def _delete_expired(conn: AsyncConnection) -> None:
    result = await conn.execute(
        """
        DELETE FROM rate_limit
        WHERE updated_at < statement_timestamp() - %s
        """,
        (_QUOTA_WINDOW,),
    )

    if result.rowcount:
        logging.debug('Deleted %d expired rate limit entries', result.rowcount)
