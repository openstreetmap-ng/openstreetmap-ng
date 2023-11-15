import logging
import time
from collections.abc import Sequence
from itertools import count

from lib.optimistic.apply import OptimisticApply
from lib.optimistic.exceptions import OptimisticError
from lib.optimistic.prepare import OptimisticPrepare
from models.db.element import Element
from models.typed_element_ref import TypedElementRef

_RETRY_TIMEOUT = 30


class Optimistic:
    def __init__(self, elements: Sequence[Element]) -> None:
        self._elements = elements

    async def update(self) -> dict[TypedElementRef, Sequence[Element]]:
        """
        Perform an optimistic update of the elements.

        Returns a mapping of original element refs to the updated elements.
        """

        if not self._elements:
            return {}

        ts = time.monotonic()

        for attempt in count(1):
            try:
                prep = OptimisticPrepare(self._elements)
                await prep.prepare()
                return await OptimisticApply.apply(prep)

            except OptimisticError:
                timeout_seconds = time.monotonic() - ts

                # retry is still possible
                if timeout_seconds < _RETRY_TIMEOUT:
                    if attempt <= 2:
                        logging.debug('Optimistic failed at attempt %d, retrying', attempt)
                    elif attempt <= 3:
                        logging.info('Optimistic failed at attempt %d, retrying', attempt, exc_info=True)
                    else:
                        logging.warning('Optimistic failed at attempt %d, retrying', attempt, exc_info=True)
                    continue

                # retry is not possible, re-raise the exception
                else:
                    logging.exception('Optimistic failed and timed out after %d attempts', attempt)
                    raise
