from hashlib import sha256

import cython
from Cryptodome.Cipher import ChaCha20

from app.config import SECRET_32bytes
from app.lib.buffered_random import buffered_randbytes

HASH_SIZE = 32


@cython.cfunc
def _hash(s: str | bytes):
    if isinstance(s, str):
        s = s.encode()
    return sha256(s)


def hash_bytes(s: str | bytes) -> bytes:
    """
    Hash a string using SHA-256.

    Optionally, provide a context to prevent hash collisions.

    Returns a buffer of the hash.
    """
    return _hash(s).digest()


def hash_hex(s: str | bytes) -> str:
    """
    Hash a string using SHA-256.

    Optionally, provide a context to prevent hash collisions.

    Returns a hex-encoded string of the hash.
    """
    return _hash(s).hexdigest()


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
