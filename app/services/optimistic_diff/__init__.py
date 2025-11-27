import asyncio
import logging
from random import uniform
from time import monotonic

import cython
from psycopg import OperationalError

from app.config import OPTIMISTIC_DIFF_RETRY_TIMEOUT
from app.db import db
from app.exceptions.optimistic_diff_error import OptimisticDiffError
from app.models.db.element import ElementInit
from app.models.element import TypedElementId
from app.services.optimistic_diff.apply import OptimisticDiffApply
from app.services.optimistic_diff.prepare import OptimisticDiffPrepare


class OptimisticDiff:
    @staticmethod
    async def run(
        elements: list[ElementInit],
    ) -> dict[TypedElementId, tuple[TypedElementId, list[int]]]:
        """
        Perform an optimistic diff update of the elements.
        Returns a dict, mapping original element refs to the new elements.
        """
        if not elements:
            return {}

        ts: cython.double = monotonic()
        sleep: cython.double = 0.05
        sleep_limit: cython.double = 5
        attempt: cython.size_t = 0

        while True:
            try:
                async with db(True) as conn:
                    prep = OptimisticDiffPrepare(conn, elements)
                    await prep.prepare()
                    return await OptimisticDiffApply.apply(prep)
            except* (OptimisticDiffError, OperationalError) as e:
                attempt += 1

                # retry is not possible, re-raise the exception
                now: cython.double = monotonic()
                timeout_seconds: cython.double = now - ts
                if timeout_seconds >= OPTIMISTIC_DIFF_RETRY_TIMEOUT.total_seconds():
                    raise TimeoutError(
                        f'OptimisticDiff failed and timed out after {attempt} attempts'
                    ) from e

                # retry is still possible
                if attempt <= 2:
                    fn = logging.debug
                elif attempt <= 3:
                    fn = logging.info
                else:
                    fn = logging.warning

                fn(
                    'OptimisticDiff failed (attempt %d), retrying',
                    attempt,
                    exc_info=True,
                )
                await asyncio.sleep(sleep)
                sleep = uniform(sleep * 1.5, sleep * 2.5)
                sleep = min(sleep, sleep_limit)
