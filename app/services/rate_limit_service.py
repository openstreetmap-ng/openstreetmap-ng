import logging
from collections.abc import Callable
from datetime import timedelta
from random import random

from fastapi import HTTPException
from psycopg import AsyncConnection
from starlette import status

from app.config import RATE_LIMIT_CLEANUP_PROBABILITY
from app.db import db
from app.services.audit_service import audit

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
    ):
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

            # probabilistic cleanup of expired entries
            if random() < RATE_LIMIT_CLEANUP_PROBABILITY:
                await _delete_expired(conn)

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


async def _delete_expired(conn: AsyncConnection):
    result = await conn.execute(
        """
        DELETE FROM rate_limit
        WHERE updated_at < statement_timestamp() - %s
        """,
        (_DEFAULT_QUOTA_WINDOW,),
    )
    if result.rowcount:
        logging.debug('Deleted %d expired rate limit entries', result.rowcount)
