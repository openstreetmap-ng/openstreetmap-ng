import base64
import logging
from hashlib import md5, pbkdf2_hmac
from hmac import compare_digest
from typing import Sequence

from argon2 import PasswordHasher

from models.user_role import UserRole


class PasswordHash:
    rehash_needed: bool | None = None

    def __init__(self, hasher: PasswordHasher):
        self._hasher = hasher

    def verify(self, hash: str, salt: str | None, password: str) -> bool:
        '''
        Verify a password against a hash and optional salt.

        Returns `True` if the password matches, `False` otherwise.

        If the password matches but the hash needs to be rehashed, `rehash_needed` will be set to `True`.
        '''

        if self.rehash_needed is not None:
            logging.warning('%r was called repeatedly', self.verify.__qualname__)

        # argon2
        if hash.startswith('$argon2'):
            if salt is not None:
                logging.warning('Unexpected salt for Argon2 hash')

            if self._hasher.verify(hash, password):
                self.rehash_needed = self._hasher.check_needs_rehash(hash)
                return True
            else:
                self.rehash_needed = False
                return False

        # rehash deprecated methods
        self.rehash_needed = True

        # md5 (deprecated)
        if len(hash) == 32:
            return compare_digest(hash, md5(((salt or '') + password).encode()).hexdigest())

        # pbkdf2 (deprecated)
        if salt and '!' in salt:
            algorithm, iterations_, salt = salt.split('!')
            iterations = int(iterations_)
            hash_buffer = base64.b64decode(hash)
            return compare_digest(hash_buffer, pbkdf2_hmac(algorithm, password.encode(), salt.encode(), iterations, len(hash_buffer)))

        hash_len = len(hash)
        salt_len = len(salt or '')
        raise ValueError(f'Unknown password hash format: {hash_len=}, {salt_len=}')

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)
