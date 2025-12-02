from hashlib import sha1
from hmac import HMAC, compare_digest
from time import time

from pydantic import SecretBytes


def _generate_totp_code(secret: SecretBytes, digits: int, time_window: int) -> str:
    """
    Generate a TOTP code for the given secret and timestamp.
    Implements RFC 6238 TOTP algorithm.
    """
    # Generate HMAC-SHA1 hash
    hmac_hash = HMAC(secret.get_secret_value(), time_window.to_bytes(8), sha1).digest()

    # Dynamic truncation
    offset = hmac_hash[-1] & 0x0F
    truncated = int.from_bytes(hmac_hash[offset : offset + 4]) & 0x7FFFFFFF

    # Generate and format code
    code = truncated % (10**digits)
    return f'{code:0{digits}d}'


def verify_totp_code(secret: SecretBytes, digits: int, code: str) -> bool:
    """
    Verify a TOTP code against the secret.

    Accepts codes from t-1, t, and t+1 time windows to account for clock drift
    and user input timing (90-second total acceptance window).
    """
    if len(code) != digits or not code.isdigit():
        return False

    # Check t-1, t, and t+1 time windows (total 90 seconds)
    time_window = totp_time_window()
    for check_time_window in (time_window, time_window - 1, time_window + 1):
        expected_code = _generate_totp_code(secret, digits, check_time_window)
        if compare_digest(code, expected_code):
            return True

    return False


def totp_time_window() -> int:
    """Get the current TOTP time window (counter value)."""
    return int(time()) // 30
