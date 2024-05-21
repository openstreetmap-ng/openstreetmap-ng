import base64
import logging
from hashlib import md5, pbkdf2_hmac
from hmac import compare_digest

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.models.str import PasswordStr
from app.models.user_role import UserRole


class PasswordHash:
    __slots__ = ('_hasher', 'rehash_needed')

    def __init__(self, hasher: PasswordHasher):
        self._hasher = hasher
        self.rehash_needed: bool | None = None

    def verify(self, password_hashed: str, salt: str | None, password: PasswordStr) -> bool:
        """
        Verify a password against a hash and optional salt.

        Returns True if the password matches, False otherwise.

        If the password matches but the hash needs to be rehashed, rehash_needed will be set to True.
        """
        if self.rehash_needed is not None:
            raise RuntimeError(f'{self.verify.__qualname__} was reused')

        # argon2
        if password_hashed.startswith('$argon2'):
            if salt is not None:
                logging.warning('Unexpected salt for argon2 password hash')

            try:
                self._hasher.verify(password_hashed, password.get_secret_value())
            except VerifyMismatchError:
                self.rehash_needed = False
                return False
            else:
                self.rehash_needed = self._hasher.check_needs_rehash(password_hashed)
                return True

        # rehash deprecated methods
        self.rehash_needed = True

        # md5 (deprecated)
        if len(password_hashed) == 32:
            valid_hash = md5(((salt or '') + password.get_secret_value()).encode()).hexdigest()  # noqa: S324
            return compare_digest(password_hashed, valid_hash)

        # pbkdf2 (deprecated)
        if (salt is not None) and '!' in salt:
            password_hashed_b = base64.b64decode(password_hashed)
            algorithm, iterations_, salt = salt.split('!')
            iterations = int(iterations_)
            valid_hash = pbkdf2_hmac(
                hash_name=algorithm,
                password=password.get_secret_value().encode(),
                salt=salt.encode(),
                iterations=iterations,
                dklen=len(password_hashed_b),
            )
            return compare_digest(password_hashed_b, valid_hash)

        hash_len = len(password_hashed)
        salt_len = len(salt or '')
        raise NotImplementedError(f'Unsupported password hash format ({hash_len=}, {salt_len=})')

    def hash(self, password: PasswordStr) -> str:
        """
        Hash a password using latest recommended algorithm.
        """
        return self._hasher.hash(password.get_secret_value())

    @classmethod
    def default(cls) -> 'PasswordHash':
        """
        Get the default password hasher.
        """
        return cls(UserRole.get_password_hasher(()))
