import base64
import logging
from hashlib import md5, pbkdf2_hmac
from hmac import compare_digest
from typing import Self

from argon2 import PasswordHasher

from src.models.user_role import UserRole


class PasswordHash:
    rehash_needed: bool | None = None

    def __init__(self, hasher: PasswordHasher):
        self._hasher = hasher

    def verify(self, password_hashed: str, salt: str | None, password: str) -> bool:
        """
        Verify a password against a hash and optional salt.

        Returns `True` if the password matches, `False` otherwise.

        If the password matches but the hash needs to be rehashed, `rehash_needed` will be set to `True`.
        """

        if self.rehash_needed is not None:
            raise RuntimeError(f'{self.verify.__qualname__} was reused')

        # argon2
        if password_hashed.startswith('$argon2'):
            if salt is not None:
                logging.warning('Unexpected salt for Argon2 hash')

            if self._hasher.verify(password_hashed, password):
                self.rehash_needed = self._hasher.check_needs_rehash(password_hashed)
                return True
            else:
                self.rehash_needed = False
                return False

        # rehash deprecated methods
        self.rehash_needed = True

        # md5 (deprecated)
        if len(password_hashed) == 32:
            valid_hash = md5(((salt or '') + password).encode()).hexdigest()  # noqa: S324
            return compare_digest(password_hashed, valid_hash)

        # pbkdf2 (deprecated)
        if salt and '!' in salt:
            password_hashed_b = base64.b64decode(password_hashed)
            algorithm, iterations_, salt = salt.split('!')
            iterations = int(iterations_)
            valid_hash = pbkdf2_hmac(algorithm, password.encode(), salt.encode(), iterations, len(password_hashed_b))
            return compare_digest(password_hashed_b, valid_hash)

        hash_len = len(password_hashed)
        salt_len = len(salt or '')
        raise ValueError(f'Unknown password hash format: {hash_len=}, {salt_len=}')

    def hash(self, password: str) -> str:  # noqa: A003
        """
        Hash a password using latest recommended algorithm.
        """

        return self._hasher.hash(password)

    @classmethod
    def default(cls) -> Self:
        """
        Get a default password hasher.
        """

        return cls(UserRole.get_password_hasher(()))
