from base64 import urlsafe_b64encode
from io import BytesIO
from os import urandom

import cython

_buffer_size = 2 * 1024 * 1024  # 2 MB
_buffer = BytesIO()


@cython.cfunc
def _randbytes(n: cython.int) -> bytes:
    buffer = _buffer
    result = buffer.read(n)
    remaining: cython.int = n - len(result)

    while remaining > 0:
        buffer.write(urandom(_buffer_size))
        buffer.seek(0)
        result += buffer.read(remaining)
        remaining = n - len(result)

    return result


def buffered_randbytes(n: int) -> bytes:
    """
    Generate a secure random byte string of length n.
    """
    return _randbytes(n)


def buffered_rand_urlsafe(n: int) -> str:
    """
    Generate a secure random URL-safe string of length n.
    """
    tok = _randbytes(n)
    return urlsafe_b64encode(tok).rstrip(b'=').decode()
