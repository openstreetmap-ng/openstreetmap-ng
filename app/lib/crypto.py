from base64 import urlsafe_b64encode
from collections.abc import Callable
from functools import lru_cache
from hashlib import sha256
from hmac import compare_digest
from typing import TypeVar

import cython
from blake3 import blake3

from app.config import CRYPTO_HASH_CACHE_MAX_ENTRIES, SECRET_32
from app.models.types import StorageKey

_T = TypeVar('_T')


@lru_cache(CRYPTO_HASH_CACHE_MAX_ENTRIES)
def _hash(s: str | bytes, key: bytes | None) -> bytes:
    return blake3(s.encode() if isinstance(s, str) else s, key=key).digest()  # pyright: ignore [reportArgumentType]


def hash_bytes(s: str | bytes) -> bytes:
    """Hash the input and return the bytes digest."""
    return _hash(s, None)


@cython.cfunc
def _hash_urlsafe(s: str | bytes) -> str:
    """Hash the input and return the URL-safe digest."""
    return urlsafe_b64encode(_hash(s, None)).rstrip(b'=').decode()


@lru_cache(maxsize=1024)
def hash_storage_key(s: str | bytes, suffix: str = '') -> StorageKey:
    """Hash the input and return the storage key."""
    return StorageKey(_hash_urlsafe(s) + suffix)


def hmac_bytes(s: str | bytes) -> bytes:
    """Compute a keyed hash of the input and return the bytes digest."""
    return _hash(s, SECRET_32.get_secret_value())


def hash_compare(
    s: _T,
    expected: bytes,
    *,
    hash_func: Callable[[_T], bytes] = hash_bytes,
) -> bool:
    """Compute and compare the hash of the input in a time-constant manner."""
    return compare_digest(hash_func(s), expected)


def hash_s256_code_challenge(verifier: str) -> str:
    """Compute the S256 code challenge from the verifier."""
    return urlsafe_b64encode(sha256(verifier.encode()).digest()).decode().rstrip('=')


# def encrypt(s: str) -> bytes:
#     """Encrypt a string using AES-CTR."""
#     assert s, 'Empty string must not be encrypted'
#     nonce = buffered_randbytes(15)  # +1 byte for the counter
#     cipher = AES.new(key=SECRET_32.get_secret_value(), mode=AES.MODE_CTR, nonce=nonce)
#     cipher_text_bytes = cipher.encrypt(s.encode())
#     return b''.join((b'\x00', nonce, cipher_text_bytes))


# def decrypt(buffer: bytes) -> str:
#     """Decrypt an encrypted buffer."""
#     if not buffer:
#         return ''

#     marker = buffer[0]
#     if marker == 0x00:
#         nonce_bytes = buffer[1:16]
#         cipher_text_bytes = buffer[16:]
#         cipher = AES.new(
#             key=SECRET_32.get_secret_value(),
#             mode=AES.MODE_CTR,
#             nonce=nonce_bytes,
#         )
#         return cipher.decrypt(cipher_text_bytes).decode()

#     raise NotImplementedError(f'Unsupported encryption marker {marker!r}')
