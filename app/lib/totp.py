"""TOTP (Time-based One-Time Password) implementation following RFC 6238."""

import secrets
import struct
import time
from base64 import b32decode, b32encode
from hashlib import sha1
from hmac import HMAC


def generate_secret() -> str:
    """
    Generate a cryptographically secure random TOTP secret.

    Returns 32-byte (256-bit) secret encoded in Base32 (52 characters).
    Compatible with all major authenticator apps.
    """
    secret_bytes = secrets.token_bytes(32)
    return b32encode(secret_bytes).decode('ascii').rstrip('=')


def generate_totp_code(secret: str, timestamp: int | None = None) -> str:
    """
    Generate a 6-digit TOTP code for the given secret and timestamp.

    Implements RFC 6238 TOTP algorithm:
    - HMAC-SHA1 hash function
    - 30-second time step
    - 6-digit output

    Args:
        secret: Base32-encoded secret key
        timestamp: Unix timestamp (default: current time)

    Returns:
        6-digit TOTP code as string
    """
    if timestamp is None:
        timestamp = int(time.time())

    # Calculate time counter (30-second intervals since Unix epoch)
    time_counter = timestamp // 30

    # Decode Base32 secret
    try:
        secret_bytes = b32decode(secret.upper() + '=' * (-len(secret) % 8))
    except Exception:
        raise ValueError('Invalid Base32 secret')

    # Generate HMAC-SHA1 hash
    time_bytes = struct.pack('>Q', time_counter)
    hmac_hash = HMAC(secret_bytes, time_bytes, sha1).digest()

    # Dynamic truncation (RFC 4226 Section 5.3)
    offset = hmac_hash[-1] & 0x0F
    truncated = struct.unpack('>I', hmac_hash[offset:offset + 4])[0] & 0x7FFFFFFF

    # Generate 6-digit code
    code = truncated % 1000000
    return f'{code:06d}'


def verify_totp_code(secret: str, code: str, timestamp: int | None = None) -> bool:
    """
    Verify a TOTP code against the secret.

    Accepts codes from t-1, t, and t+1 time windows to account for clock drift
    and user input timing (90-second total acceptance window).

    Args:
        secret: Base32-encoded secret key
        code: 6-digit code to verify
        timestamp: Unix timestamp (default: current time)

    Returns:
        True if code is valid, False otherwise
    """
    if not code or len(code) != 6 or not code.isdigit():
        return False

    if timestamp is None:
        timestamp = int(time.time())

    # Check t-1, t, and t+1 time windows (total 90 seconds)
    for offset in [-1, 0, 1]:
        window_timestamp = timestamp + (offset * 30)
        expected_code = generate_totp_code(secret, window_timestamp)
        if secrets.compare_digest(code, expected_code):
            return True

    return False


def get_time_window(timestamp: int | None = None) -> int:
    """
    Get the current TOTP time window (counter value).

    Used for replay prevention - each time window is 30 seconds.

    Args:
        timestamp: Unix timestamp (default: current time)

    Returns:
        Time window counter (timestamp // 30)
    """
    if timestamp is None:
        timestamp = int(time.time())
    return timestamp // 30
