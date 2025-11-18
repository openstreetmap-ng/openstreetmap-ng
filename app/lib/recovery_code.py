from hmac import compare_digest

import cython
from blake3 import blake3
from pydantic import SecretBytes

# Crockford Base32 alphabet (no I, L, O, U to avoid ambiguity)
_ENC = b'0123456789ABCDEFGHJKMNPQRSTVWXYZ'

# Maps ASCII (0-255) directly to values 0-31
_DEC: list[int | None] = [None] * 256

# Standard mapping
for i, char in enumerate(_ENC):
    _DEC[char] = i
for i, char in enumerate(_ENC.lower()):
    _DEC[char] = i

# Normalization mapping
for char, val in [
    (b'O'[0], 0),
    (b'I'[0], 1),
    (b'L'[0], 1),
    (b'U'[0], _ENC.index(b'V')),
]:
    _DEC[char] = val
    _DEC[char + 32] = val  # lowercase


@cython.cfunc
def _encode_code(value: int) -> str:
    """Encodes 50 bits to 'XXXXX-XXXXX'"""
    buf = bytearray(10)
    for i in range(9, -1, -1):
        buf[i] = _ENC[value & 31]
        value >>= 5
    return f'{buf[:5].decode()}-{buf[5:].decode()}'


@cython.cfunc
def _decode_code(code: str) -> int:
    value = 0
    for b in code.encode('ascii', 'ignore'):
        v = _DEC[b]
        if v is not None:
            value = (value << 5) | v
    return value


def generate_recovery_codes(secret: SecretBytes, base_index: int) -> list[str]:
    """Generate all 8 recovery codes for a given base index."""
    hasher = blake3(secret.get_secret_value(), derive_key_context=str(base_index))
    stream = hasher.digest(48)
    return [
        _encode_code(
            (offset << 47) | (int.from_bytes(stream[i : i + 6]) & ((1 << 47) - 1))
        )
        for offset, i in enumerate(range(0, 48, 6))
    ]


def verify_recovery_code(secret: SecretBytes, base_index: int, code: str) -> int | None:
    """Verify a recovery code and return its offset if valid."""
    code_bits = _decode_code(code)

    # Check if offset is in valid range (0-7)
    offset = code_bits >> 47
    if offset > 7:
        return None

    input_bytes = (code_bits & ((1 << 47) - 1)).to_bytes(6)

    hasher = blake3(secret.get_secret_value(), derive_key_context=str(base_index))
    expected_bytes = bytearray(hasher.digest(6, seek=offset * 6))
    expected_bytes[0] &= 0x7F

    return offset if compare_digest(input_bytes, expected_bytes) else None
