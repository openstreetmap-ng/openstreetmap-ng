from base64 import urlsafe_b64encode
from collections import OrderedDict
from collections.abc import Callable
from hashlib import sha256
from hmac import compare_digest
from typing import TypeVar

import cython
from blake3 import blake3
from Crypto.Cipher import AES
from pydantic import SecretBytes

from app.config import (
    CRYPTO_HASH_CACHE_MAX_ENTRIES,
    CRYPTO_HASH_CACHE_SIZE_LIMIT,
    SECRET_32,
)
from app.models.types import StorageKey
from speedup.buffered_rand import buffered_randbytes

_T = TypeVar('_T')


@cython.cfunc
def _hash(
    s: str | bytes,
    key: bytes | None,
    size: int,
    *,
    CRYPTO_HASH_CACHE_MAX_ENTRIES: cython.size_t = CRYPTO_HASH_CACHE_MAX_ENTRIES,
    CRYPTO_HASH_CACHE_SIZE_LIMIT: cython.size_t = CRYPTO_HASH_CACHE_SIZE_LIMIT,
    _CACHE=OrderedDict[tuple[str | bytes, bytes | None, int], bytes](),
) -> bytes:
    use_cache: cython.bint = len(s) < CRYPTO_HASH_CACHE_SIZE_LIMIT

    # Check cache first
    if use_cache:
        cache_key = (s, key, size)
        result = _CACHE.get(cache_key)
        if result is not None:
            _CACHE.move_to_end(cache_key)
            return result

    # Compute hash
    result = blake3(s.encode() if isinstance(s, str) else s, key=key).digest(size)  # pyright: ignore[reportArgumentType]

    # Cache if below size limit
    if use_cache:
        _CACHE[cache_key] = result  # pyright: ignore[reportPossiblyUnboundVariable]
        if len(_CACHE) > CRYPTO_HASH_CACHE_MAX_ENTRIES:
            _CACHE.popitem(last=False)

    return result


def hash_bytes(s: str | bytes, size: int = 32) -> bytes:
    """Hash the input and return the bytes digest."""
    return _hash(s, None, size)


def hash_parts(parts: list[str | bytes], size: int = 16) -> bytes:
    """Hash a list of parts into a hashed digest."""
    return _hash(
        b'\0'.join(
            part.encode() if isinstance(part, str) else part  #
            for part in parts
        ),
        None,
        size,
    )


@cython.cfunc
def _hash_urlsafe(s: str | bytes) -> str:
    """Hash the input and return the URL-safe digest."""
    return urlsafe_b64encode(_hash(s, None, 32)).rstrip(b'=').decode()


def hash_storage_key(s: str | bytes, suffix: str = '') -> StorageKey:
    """Hash the input and return the storage key."""
    return StorageKey(_hash_urlsafe(s) + suffix)


def hmac_bytes(s: str | bytes, size: int = 32) -> bytes:
    """Compute a keyed hash of the input and return the bytes digest."""
    return _hash(s, SECRET_32.get_secret_value(), size)


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


def encrypt(s: SecretBytes) -> bytes:
    """Encrypt a string using AES-CTR."""
    assert s, 'Empty string must not be encrypted'
    nonce = buffered_randbytes(15)  # +1 byte for the counter
    cipher = AES.new(key=SECRET_32.get_secret_value(), mode=AES.MODE_CTR, nonce=nonce)
    cipher_text_bytes = cipher.encrypt(s.get_secret_value())
    return b''.join((b'\x00', nonce, cipher_text_bytes))


def decrypt(buffer: bytes) -> SecretBytes:
    """Decrypt an encrypted buffer."""
    if not buffer:
        return SecretBytes(b'')

    marker = buffer[0]
    if marker == 0x00:
        nonce_bytes = buffer[1:16]
        cipher_text_bytes = buffer[16:]
        cipher = AES.new(
            key=SECRET_32.get_secret_value(),
            mode=AES.MODE_CTR,
            nonce=nonce_bytes,
        )
        return SecretBytes(cipher.decrypt(cipher_text_bytes))

    raise NotImplementedError(f'Unsupported encryption marker {marker!r}')
