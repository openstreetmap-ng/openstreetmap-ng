from time import time_ns
from uuid import UUID

import cython

from app.lib.buffered_random import buffered_randbytes

_last_time: int = 0
_last_seq: int = -1

# UUIDv7 Field and Bit Layout - Encoding Example (Millisecond Precision)
# see: https://www.ietf.org/archive/id/draft-peabody-dispatch-new-uuid-format-01.html#name-uuidv7-layout-and-bit-order
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                            unixts                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |unixts |         msec          |  ver  |          seq          |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |var|                         rand                              |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                             rand                              |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


def uuid7() -> UUID:
    global _last_time, _last_seq

    ns: cython.uint = 1_000_000_000
    ms: cython.uint = 1_000_000

    time: cython.ulonglong = time_ns()

    # truncate to millisecond precision
    time = (time // ms) * ms

    # get the unix timestamp in seconds
    unixts: cython.ulonglong = time // ns

    # get the milliseconds
    msec: cython.uint = (time % ns) // ms

    # get the sequence number (increment if the time is unchanged)
    seq: cython.int
    if _last_time == time:
        seq = _last_seq
        seq += 1
        _last_seq = seq
    else:
        seq = 0
        _last_time = time
        _last_seq = seq

    rand: cython.ulonglong = int.from_bytes(buffered_randbytes(8))

    # truncate first 2 bits
    trun: cython.ulonglong = 0x3FFFFFFFFFFFFFFF
    rand = rand & trun

    uuid_int: int = (
        (unixts << (128 - 36))
        + (msec << (128 - 36 - 12))
        + (7 << (128 - 36 - 12 - 4))  # version
        + (seq << 64)
        + (2 << 62)  # variant
        + rand
    )

    return UUID(int=uuid_int)
