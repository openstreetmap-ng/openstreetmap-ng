import secrets
from base64 import urlsafe_b64encode
from hashlib import sha256
from hmac import HMAC

from Crypto.Cipher import ChaCha20

from config import SECRET_32b


def _hash(s: str | bytes, *, context: str | None):
    if isinstance(s, str):
        s = s.encode()

    if context is None:
        return sha256(s)
    else:
        return HMAC(context.encode(), s, sha256)


def hash_hex(s: str | bytes, *, context: str | None) -> str:
    return _hash(s, context=context).hexdigest()


def hash_urlsafe(s: str | bytes, *, context: str | None) -> str:
    return urlsafe_b64encode(_hash(s, context=context).digest()).decode()


def encrypt_hex(s: str) -> str:
    '''
    Encrypt a string using XChaCha20.

    Returns a hex-encoded string of the nonce and ciphertext.
    '''

    nonce_b = secrets.token_bytes(24)
    cipher = ChaCha20.new(key=SECRET_32b, nonce=nonce_b)
    ciphertext_b = cipher.encrypt(s.encode())
    return nonce_b.hex() + ciphertext_b.hex()


def decrypt_hex(s: str) -> str:
    '''
    Decrypt a string using XChaCha20.

    Expects a hex-encoded string of the nonce and ciphertext.
    '''

    nonce_b = bytes.fromhex(s[:48])
    ciphertext_b = bytes.fromhex(s[48:])
    cipher = ChaCha20.new(key=SECRET_32b, nonce=nonce_b)
    return cipher.decrypt(ciphertext_b).decode()
