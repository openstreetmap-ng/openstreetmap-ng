import base64
import logging
from hashlib import md5, pbkdf2_hmac
from hmac import compare_digest

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from argon2.profiles import RFC_9106_LOW_MEMORY

from app.models.str import PasswordStr

_hasher = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)


class PasswordHash:
    __slots__ = ('rehash_needed',)

    def __init__(self):
        self.rehash_needed: bool | None = None

    def verify(self, password_hashed: str, extra: str | None, password: PasswordStr) -> bool:
        """
        Verify a password against a hash and optional extra data.

        Returns True if the password matches, False otherwise.

        If the password matches but the hash needs to be rehashed, rehash_needed will be set to True.
        """
        # argon2
        if password_hashed.startswith('$argon2'):
            if extra is not None:
                logging.warning('Unexpected salt for argon2 password hash')

            try:
                _hasher.verify(password_hashed, password.get_secret_value())
            except VerifyMismatchError:
                self.rehash_needed = False
                return False
            else:
                self.rehash_needed = _hasher.check_needs_rehash(password_hashed)
                return True

        # rehash deprecated methods
        self.rehash_needed = True

        # md5 (deprecated)
        if len(password_hashed) == 32:
            salt = extra or ''
            valid_hash = md5((salt + password.get_secret_value()).encode()).hexdigest()  # noqa: S324
            return compare_digest(password_hashed, valid_hash)

        # pbkdf2 (deprecated)
        if (extra is not None) and '!' in extra:
            password_hashed_b = base64.b64decode(password_hashed)
            algorithm, iterations_, salt = extra.split('!')
            iterations = int(iterations_)
            valid_hash = pbkdf2_hmac(
                hash_name=algorithm,
                password=password.get_secret_value().encode(),
                salt=salt.encode(),
                iterations=iterations,
                dklen=len(password_hashed_b),
            )
            return compare_digest(password_hashed_b, valid_hash)

        raise NotImplementedError(
            f'Unsupported password hash format: {password_hashed[:10]}***, len={len(password_hashed)}'
        )

    @staticmethod
    def hash(password: PasswordStr) -> str:
        """
        Hash a password using latest recommended algorithm.
        """
        return _hasher.hash(password.get_secret_value())

    @staticmethod
    def client_prehash(password: PasswordStr) -> str:
        """
        Prehash a password using the client's algorithm.
        """
        return pbkdf2_hmac(
            hash_name='sha256',
            password=password.get_secret_value().encode(),
            salt=b'',
            iterations=20_000,
        ).hex()
