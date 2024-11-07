from base64 import urlsafe_b64encode
from hashlib import sha256
from hmac import HMAC

import cython
from Cryptodome.Cipher import AES

from app.config import SECRET_32
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

    Returns a buffer of the hash.
    """
    return _hash(s).digest()


def hash_hex(s: str | bytes) -> str:
    """
    Hash a string using SHA-256.

    Returns a hex-encoded string of the hash.
    """
    return _hash(s).hexdigest()


def hash_s256_code_challenge(verifier: str) -> str:
    """
    Compute the S256 code challenge from the verifier.
    """
    return urlsafe_b64encode(sha256(verifier.encode()).digest()).decode().rstrip('=')


def hmac_bytes(s: bytes) -> bytes:
    """
    Compute the HMAC of a string using SHA-256 and the app secret.
    """
    return HMAC(SECRET_32, s, sha256).digest()


def encrypt(s: str) -> bytes:
    """
    Encrypt a string using AES-CTR.
    """
    if not s:
        raise AssertionError('Empty string must not be encrypted')
    nonce = buffered_randbytes(15)  # +1 byte for the counter
    cipher = AES.new(key=SECRET_32, mode=AES.MODE_CTR, nonce=nonce)
    cipher_text_bytes = cipher.encrypt(s.encode())
    return b''.join((b'\x00', nonce, cipher_text_bytes))


def decrypt(buffer: bytes) -> str:
    """
    Decrypt an encrypted buffer.
    """
    if not buffer:
        return ''
    marker = buffer[0]
    if marker == 0x00:
        nonce_bytes = buffer[1:16]
        cipher_text_bytes = buffer[16:]
        cipher = AES.new(key=SECRET_32, mode=AES.MODE_CTR, nonce=nonce_bytes)
        return cipher.decrypt(cipher_text_bytes).decode()
    raise NotImplementedError(f'Unsupported encryption marker {marker!r}')
