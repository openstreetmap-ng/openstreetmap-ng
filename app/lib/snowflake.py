from time import time_ns

import cython

from app.lib.buffered_random import buffered_randbytes

_last_time: int = -1
_last_seq: int = -1

# Mastodon-inspired, Snowflake ID
# 1 bit zero, 47 bits timestamp, 16 bits random+sequence


def snowflake_id() -> int:
    global _last_time, _last_seq

    time_max: cython.ulonglong = 0x7FFFFFFFFFFF
    time: cython.ulonglong = time_ns()

    # get the time in milliseconds
    time = time // 1_000_000

    if time > time_max:
        raise OverflowError('Time value is too large')

    # get the sequence number (increment if the time is unchanged)
    seq_max: cython.ushort = 0xFFFF
    seq: cython.ushort
    if _last_time == time:
        seq = _last_seq

        if seq < seq_max:
            seq += 1
        else:
            seq = 0

        _last_seq = seq
    else:
        seq = int.from_bytes(buffered_randbytes(2))
        _last_time = time
        _last_seq = seq

    return (time << 16) | seq
