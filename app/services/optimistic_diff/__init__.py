import logging
import time
from collections.abc import Sequence

import cython
from sqlalchemy.exc import IntegrityError

from app.exceptions.optimistic_diff_error import OptimisticDiffError
from app.limits import OPTIMISTIC_DIFF_RETRY_TIMEOUT
from app.models.db.element import Element
from app.models.element_ref import ElementRef
from app.services.optimistic_diff.apply import OptimisticDiffApply
from app.services.optimistic_diff.prepare import OptimisticDiffPrepare


class OptimisticDiff:
    __slots__ = ('_elements',)

    def __init__(self, elements: Sequence[Element]) -> None:
        self._elements = elements

    async def run(self) -> dict[ElementRef, Sequence[Element]]:
        """
        Perform an optimistic diff update of the elements.

        Returns a dict, mapping original element refs to the new elements.
        """

        if not self._elements:
            return {}

        ts = time.monotonic()
        attempt: cython.int = 0

        while True:
            attempt += 1

            try:
                prep = OptimisticDiffPrepare(self._elements)
                await prep.prepare()
                return await OptimisticDiffApply().apply(prep)

            except (OptimisticDiffError, IntegrityError) as e:
                timeout_seconds = time.monotonic() - ts

                # retry is still possible
                if timeout_seconds < OPTIMISTIC_DIFF_RETRY_TIMEOUT.total_seconds():
                    if attempt <= 2:
                        fn = logging.debug
                    elif attempt <= 3:
                        fn = logging.info
                    else:
                        fn = logging.warning

                    fn('OptimisticDiff failed (attempt %d), retrying', attempt, exc_info=True)
                    continue

                # retry is not possible, re-raise the exception
                raise TimeoutError(f'OptimisticDiff failed and timed out after {attempt} attempts') from e
