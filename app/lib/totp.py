from base64 import b32decode
from hashlib import sha1
from hmac import HMAC, compare_digest
from time import time

import cython
from pydantic import SecretStr


@cython.cfunc
def _generate_totp_code(secret: SecretStr, time_window: int) -> str:
    """
    Generate a 6-digit TOTP code for the given secret and timestamp.
    Implements RFC 6238 TOTP algorithm.
    """
    try:
        secret_value = secret.get_secret_value()
        secret_bytes = b32decode(secret_value.upper() + '=' * (-len(secret_value) % 8))
    except Exception as e:
        raise ValueError('Invalid Base32 secret') from e

    # Generate HMAC-SHA1 hash
    hmac_hash = HMAC(secret_bytes, time_window.to_bytes(8), sha1).digest()
    del secret_value, secret_bytes

    # Dynamic truncation
    offset = hmac_hash[-1] & 0x0F
    truncated = int.from_bytes(hmac_hash[offset : offset + 4]) & 0x7FFFFFFF

    # Generate 6-digit code
    code = truncated % 1000000
    return f'{code:06d}'


def verify_totp_code(secret: SecretStr, code: str) -> bool:
    """
    Verify a TOTP code against the secret.

    Accepts codes from t-1, t, and t+1 time windows to account for clock drift
    and user input timing (90-second total acceptance window).
    """
    if len(code) != 6 or not code.isdigit():
        return False

    # Check t-1, t, and t+1 time windows (total 90 seconds)
    time_window = totp_time_window()
    for check_time_window in (time_window, time_window - 1, time_window + 1):
        expected_code = _generate_totp_code(secret, check_time_window)
        if compare_digest(code, expected_code):
            return True

    return False


def totp_time_window() -> int:
    """Get the current TOTP time window (counter value)."""
    return int(time()) // 30
