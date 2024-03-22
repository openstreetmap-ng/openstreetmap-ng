from base64 import urlsafe_b64encode
from hashlib import sha256
from hmac import HMAC

import cython
from Cryptodome.Cipher import ChaCha20

from app.config import SECRET_32bytes
from app.lib.buffered_random import buffered_randbytes

HASH_SIZE = 32


@cython.cfunc
def _hash(s: str | bytes, *, context: str | None):
    if isinstance(s, str):
        s = s.encode()

    if context is None:
        return sha256(s)
    else:
        return HMAC(context.encode(), s, sha256)


def hash_bytes(s: str | bytes, *, context: str | None) -> bytes:
    """
    Hash a string using SHA-256.

    Optionally, provide a context to prevent hash collisions.

    Returns a buffer of the hash.
    """
    return _hash(s, context=context).digest()


def hash_hex(s: str | bytes, *, context: str | None) -> str:
    """
    Hash a string using SHA-256.

    Optionally, provide a context to prevent hash collisions.

    Returns a hex-encoded string of the hash.
    """
    return _hash(s, context=context).hexdigest()


def hash_urlsafe(s: str | bytes, *, context: str | None) -> str:
    """
    Hash a string using SHA-256.

    Optionally, provide a context to prevent hash collisions.

    Returns a URL-safe base64-encoded string of the hash.
    """
    return urlsafe_b64encode(_hash(s, context=context).digest()).decode()


def encrypt(s: str) -> bytes:
    """
    Encrypt a string using XChaCha20.

    Returns a buffer of the nonce and cipher text.
    """
    nonce_bytes = buffered_randbytes(24)
    cipher = ChaCha20.new(key=SECRET_32bytes, nonce=nonce_bytes)
    cipher_text_bytes = cipher.encrypt(s.encode())
    return nonce_bytes + cipher_text_bytes


def decrypt(buffer: bytes) -> str:
    """
    Decrypt a buffer using XChaCha20.

    Expects a buffer of the nonce and cipher text.
    """
    nonce_bytes = buffer[:24]
    cipher_text_bytes = buffer[24:]
    cipher = ChaCha20.new(key=SECRET_32bytes, nonce=nonce_bytes)
    return cipher.decrypt(cipher_text_bytes).decode()
