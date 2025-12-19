from hmac import compare_digest

import cython

from app.lib.crypto import hash_bytes
from speedup import buffered_randbytes

# Base58 alphabet
_ENC = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
_DEC: list[int | None] = [None] * 256

for i, char in enumerate(_ENC):
    _DEC[char] = i


@cython.cfunc
def _encode_code(value: int) -> str:
    """Encodes 70 bits to 'XXXX-XXXX-XXXX'"""
    buf = bytearray(12)
    for i in range(11, -1, -1):
        buf[i] = _ENC[value % 58]
        value //= 58
    return f'{buf[:4].decode()}-{buf[4:8].decode()}-{buf[8:].decode()}'


@cython.cfunc
def _decode_code(code: str) -> int:
    value = 0
    for b in code.encode('ascii', 'ignore'):
        v = _DEC[b]
        if v is not None:
            value = value * 58 + v
    return value


def generate_recovery_codes() -> tuple[list[str], list[bytes]]:
    """
    Generate 8 new recovery codes.
    Returns (list of display codes, list of hashes for storage).
    """
    stream = buffered_randbytes(9 * 8)
    display_codes = []
    codes_hashed = []

    for i in range(8):
        offset = i * 9
        rand_int = int.from_bytes(stream[offset : offset + 9]) & ((1 << 67) - 1)
        display_codes.append(_encode_code((i << 67) | rand_int))
        codes_hashed.append(hash_bytes(rand_int.to_bytes(9), size=9))

    return display_codes, codes_hashed


def verify_recovery_code(code: str, codes_hashed: list[bytes | None]) -> int | None:
    """
    Verify a recovery code.
    Returns the index if valid, or None.
    """
    val = _decode_code(code)

    index = val >> 67
    if index > 7:
        return None

    stored_hash = codes_hashed[index]
    if stored_hash is None:
        return None

    rand_int = val & ((1 << 67) - 1)
    expected_hash = hash_bytes(rand_int.to_bytes(9), size=9)
    return index if compare_digest(expected_hash, stored_hash) else None
