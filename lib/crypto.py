import secrets
from base64 import urlsafe_b64encode
from hashlib import sha256
from hmac import HMAC

from Crypto.Cipher import ChaCha20

from config import SECRET_32b

HASH_SIZE = 32


def _hash(s: str | bytes, *, context: str | None):
    if isinstance(s, str):
        s = s.encode()

    if context is None:
        return sha256(s)
    else:
        return HMAC(context.encode(), s, sha256)


def hash_b(s: str | bytes, *, context: str | None) -> bytes:
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


def encrypt_b(s: str) -> bytes:
    """
    Encrypt a string using XChaCha20.

    Returns a buffer of the nonce and ciphertext.
    """

    nonce_b = secrets.token_bytes(24)
    cipher = ChaCha20.new(key=SECRET_32b, nonce=nonce_b)
    ciphertext_b = cipher.encrypt(s.encode())
    return nonce_b + ciphertext_b


def decrypt_b(b: bytes) -> str:
    """
    Decrypt a buffer using XChaCha20.

    Expects a buffer of the nonce and ciphertext.
    """

    nonce_b = b[:24]
    ciphertext_b = b[24:]
    cipher = ChaCha20.new(key=SECRET_32b, nonce=nonce_b)
    return cipher.decrypt(ciphertext_b).decode()
