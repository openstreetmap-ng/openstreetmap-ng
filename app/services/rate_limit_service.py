import asyncio
import logging
from asyncio import Event, TaskGroup
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import timedelta
from random import uniform
from time import monotonic

from fastapi import HTTPException
from sentry_sdk import start_transaction
from starlette import status

from app.db import db, db_lock
from app.lib.retry import retry
from app.lib.sentry import (
    SENTRY_RATE_LIMIT_MANAGEMENT_MONITOR,
    SENTRY_RATE_LIMIT_MANAGEMENT_MONITOR_SLUG,
)
from app.lib.testmethod import testmethod
from app.services.audit_service import audit

_PROCESS_REQUEST_EVENT = Event()
_PROCESS_DONE_EVENT = Event()

_DEFAULT_QUOTA_WINDOW = timedelta(hours=1)


class RateLimitService:
    @staticmethod
    async def update(
        key: str,
        change: float,
        quota: float,
        *,
        window: timedelta = _DEFAULT_QUOTA_WINDOW,
        raise_on_limit: str | Callable[[], str] | None = 'Rate limit exceeded',
    ) -> dict[str, str]:
        """
        Update the rate limit counter and check if the limit is exceeded.
        Returns the response headers or raises a HTTPException.
        """
        assert window is _DEFAULT_QUOTA_WINDOW or window <= _DEFAULT_QUOTA_WINDOW
        quota_window_seconds = window.total_seconds()
        quota_per_second = quota / quota_window_seconds

        # Uses a leaky bucket algorithm where the usage decreases over time.
        async with (
            db(True) as conn,
            await conn.execute(
                """
                INSERT INTO rate_limit (key, usage)
                VALUES (%(key)s, %(change)s)
                ON CONFLICT (key) DO UPDATE SET
                    usage = GREATEST(
                        rate_limit.usage -
                        EXTRACT(EPOCH FROM (statement_timestamp() - rate_limit.updated_at)) * %(quota_per_second)s,
                        0
                    ) + EXCLUDED.usage,
                    updated_at = DEFAULT
                RETURNING usage
                """,
                {'key': key, 'change': change, 'quota_per_second': quota_per_second},
            ) as r,
        ):
            usage: float = (await r.fetchone())[0]  # type: ignore

        # Prepare headers
        quota_remaining = max(quota - usage, 0)
        reset_seconds = usage / quota_per_second
        headers = {
            'RateLimit': f'"default";r={quota_remaining:.0f};t={reset_seconds:.0f}',
            'RateLimit-Policy': f'"default";q={quota:.0f};w={quota_window_seconds:.0f}',
        }

        # Check if the limit is exceeded
        if usage > quota:
            audit('rate_limit').close()
            if raise_on_limit is not None:
                if not isinstance(raise_on_limit, str):
                    raise_on_limit = raise_on_limit()
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=raise_on_limit,
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
    async def sleep(delay: float) -> None:
        if delay > 0:
            try:
                await asyncio.wait_for(_PROCESS_REQUEST_EVENT.wait(), timeout=delay)
            except TimeoutError:
                pass

    while True:
        async with db_lock(8569304793767999080) as acquired:
            if acquired:
                _PROCESS_REQUEST_EVENT.clear()

                ts = monotonic()
                with (
                    SENTRY_RATE_LIMIT_MANAGEMENT_MONITOR,
                    start_transaction(
                        op='task', name=SENTRY_RATE_LIMIT_MANAGEMENT_MONITOR_SLUG
                    ),
                ):
                    await _delete_expired()
                tt = monotonic() - ts

                if not _PROCESS_REQUEST_EVENT.is_set():
                    _PROCESS_DONE_EVENT.set()

                # on success, sleep ~5min
                await sleep(uniform(290, 310) - tt)
            else:
                # on failure, sleep ~1h
                await sleep(uniform(0.5 * 3600, 1.5 * 3600))


async def _delete_expired() -> None:
    async with db(True) as conn:
        result = await conn.execute(
            """
            DELETE FROM rate_limit
            WHERE updated_at < statement_timestamp() - %s
            """,
            (_DEFAULT_QUOTA_WINDOW,),
        )
        if result.rowcount:
            logging.debug('Deleted %d expired rate limit entries', result.rowcount)
