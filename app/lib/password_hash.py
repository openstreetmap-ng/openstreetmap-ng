import base64
from hashlib import md5, pbkdf2_hmac
from hmac import compare_digest
from typing import NamedTuple

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from argon2.profiles import RFC_9106_LOW_MEMORY

from app.config import TEST_ENV
from app.models.types import PasswordType


class VerifyResult(NamedTuple):
    success: bool
    rehash_needed: bool


_hasher = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)


class PasswordHash:
    @staticmethod
    def verify(password_hashed: str, password: PasswordType, *, is_test_user: bool) -> VerifyResult:
        """
        Verify a password against a hash and optional extra data.
        """
        # test user accepts any password in test environment
        if is_test_user:
            return VerifyResult(success=TEST_ENV, rehash_needed=False)

        # argon2
        if password_hashed.startswith('$argon2'):
            try:
                _hasher.verify(password_hashed, password.get_secret_value())
            except VerifyMismatchError:
                return VerifyResult(False, False)
            else:
                rehash_needed = _hasher.check_needs_rehash(password_hashed)
                return VerifyResult(True, rehash_needed)

        password_hashed, _, extra = password_hashed.partition('.')

        # md5 (deprecated)
        if len(password_hashed) == 32:
            salt = extra or ''
            valid_hash = md5((salt + password.get_secret_value()).encode()).hexdigest()  # noqa: S324
            success = compare_digest(password_hashed, valid_hash)
            return VerifyResult(success, True)

        # pbkdf2 (deprecated)
        if '!' in extra:
            password_hashed_b = base64.b64decode(password_hashed)
            algorithm, iterations_, salt = extra.split('!')
            iterations = int(iterations_)
            valid_hash_b = pbkdf2_hmac(
                hash_name=algorithm,
                password=password.get_secret_value().encode(),
                salt=salt.encode(),
                iterations=iterations,
                dklen=len(password_hashed_b),
            )
            success = compare_digest(password_hashed_b, valid_hash_b)
            return VerifyResult(success, True)

        raise NotImplementedError(
            f'Unsupported password hash format: {password_hashed[:10]}***, len={len(password_hashed)}'
        )

    @staticmethod
    def hash(password: PasswordType) -> str:
        """
        Hash a password using latest recommended algorithm.
        """
        return _hasher.hash(password.get_secret_value())
