import logging
import time
from collections.abc import Collection

import cython
from sqlalchemy.exc import IntegrityError

from app.exceptions.optimistic_diff_error import OptimisticDiffError
from app.limits import OPTIMISTIC_DIFF_RETRY_TIMEOUT
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.services.optimistic_diff.apply import OptimisticDiffApply
from app.services.optimistic_diff.prepare import OptimisticDiffPrepare


class OptimisticDiff:
    @staticmethod
    async def run(elements: Collection[Element]) -> dict[ElementRef, list[Element]]:
        """
        Perform an optimistic diff update of the elements.

        Returns a dict, mapping original element refs to the new elements.
        """
        if not elements:
            return {}

        ts = time.monotonic()
        attempt: cython.int = 0

        while True:
            attempt += 1

            try:
                prep = OptimisticDiffPrepare(elements)
                await prep.prepare()
                return await OptimisticDiffApply().apply(prep)

            except (OptimisticDiffError, IntegrityError) as e:
                timeout_seconds = time.monotonic() - ts

                # retry is not possible, re-raise the exception
                if timeout_seconds >= OPTIMISTIC_DIFF_RETRY_TIMEOUT.total_seconds():
                    raise TimeoutError(f'OptimisticDiff failed and timed out after {attempt} attempts') from e

                # retry is still possible
                if attempt <= 2:
                    fn = logging.debug
                elif attempt <= 3:
                    fn = logging.info
                else:
                    fn = logging.warning

                fn('OptimisticDiff failed (attempt %d), retrying', attempt, exc_info=True)
