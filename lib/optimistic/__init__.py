import logging
import time
from itertools import count
from typing import Sequence

from lib.optimistic.apply import OptimisticApply
from lib.optimistic.exceptions import OptimisticException
from lib.optimistic.prepare import OptimisticPrepare
from models.collections.element import Element
from models.typed_element_ref import TypedElementRef

_RETRY_TIMEOUT = 30


class Optimistic:
    def __init__(self, elements: Sequence[Element]) -> None:
        self._elements = elements

    # TODO: return assigned ids
    async def update(self) -> dict[TypedElementRef, Sequence[Element]]:
        if not self._elements:
            return {}

        ts = time.perf_counter()

        for attempt in count(1):
            try:
                prepare = OptimisticPrepare(self._elements)
                await prepare.prepare()
                return await OptimisticApply.apply(prepare)
            except OptimisticException as e:
                if time.perf_counter() - ts < _RETRY_TIMEOUT:
                    message = f'OptimisticException attempt {attempt}, retrying optimistic update...'
                    if attempt <= 2:
                        logging.debug(message)
                    elif attempt <= 3:
                        logging.info(message, exc_info=True)
                    else:
                        logging.warning(message, exc_info=True)
                    continue
                else:
                    logging.error(f'OptimisticException attempt {attempt}, retry timeout exceeded', exc_info=True)
                    raise TimeoutError(f'{self.__class__.__qualname__} update retry timeout exceeded') from e
