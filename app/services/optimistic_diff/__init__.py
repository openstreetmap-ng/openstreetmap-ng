import logging
import time
from collections.abc import Sequence
from itertools import count

from sqlalchemy.exc import IntegrityError

from app.exceptions.optimistic_diff_error import OptimisticDiffError
from app.limits import OPTIMISTIC_DIFF_RETRY_TIMEOUT
from app.models.db.element import Element
from app.models.typed_element_ref import TypedElementRef
from app.services.optimistic_diff.apply import OptimisticDiffApply
from app.services.optimistic_diff.prepare import OptimisticDiffPrepare


class OptimisticDiff:
    def __init__(self, elements: Sequence[Element]) -> None:
        self._elements = elements

    async def update(self) -> dict[TypedElementRef, Sequence[Element]]:
        """
        Perform an optimistic update of the elements.

        Returns a dict, mapping original typed refs to the new elements.
        """

        if not self._elements:
            return {}

        ts = time.monotonic()

        for attempt in count(1):
            try:
                prep = OptimisticDiffPrepare(self._elements)
                await prep.prepare()
                return await OptimisticDiffApply().apply(prep)

            except (OptimisticDiffError, IntegrityError):
                timeout_seconds = time.monotonic() - ts

                # retry is still possible
                if timeout_seconds < OPTIMISTIC_DIFF_RETRY_TIMEOUT.total_seconds():
                    if attempt <= 2:
                        logging.debug('Optimistic diff failed at attempt %d, retrying', attempt)
                    elif attempt <= 3:
                        logging.info('Optimistic diff failed at attempt %d, retrying', attempt, exc_info=True)
                    else:
                        logging.warning('Optimistic diff failed at attempt %d, retrying', attempt, exc_info=True)
                    continue

                # retry is not possible, re-raise the exception
                else:
                    logging.exception('Optimistic diff failed and timed out after %d attempts', attempt)
                    raise
