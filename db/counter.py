import logging
from typing import Sequence

from motor.core import AgnosticClientSession

from db import MONGO_DB

_COUNTER_COLLECTION = MONGO_DB['counters']
# TODO: unique index


async def get_next_sequence(name: str, n: int, session: AgnosticClientSession | None) -> Sequence[int]:
    if not n:
        return ()

    doc = await _COUNTER_COLLECTION.find_one_and_update(
        {'_id': name},
        {'$inc': {'seq': n}},
        new=True,
        upsert=True,
        session=session
    )

    logging.debug('Incremented counter %r by %d to %d', name, n, doc['seq'])

    if n == 1:
        return (doc['seq'],)
    else:
        return tuple(range(doc['seq'] - n + 1, doc['seq'] + 1))
