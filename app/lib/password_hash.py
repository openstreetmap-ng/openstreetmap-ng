import logging
from base64 import b64decode, b64encode
from hashlib import md5, pbkdf2_hmac
from hmac import compare_digest
from typing import Literal, NamedTuple

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError

from app.config import TEST_ENV
from app.models.proto.server_pb2 import UserPassword
from app.models.types import PasswordType

PasswordSchema = Literal['legacy', 'v1']

__all__ = ('PasswordSchema',)


class VerifyResult(NamedTuple):
    success: bool
    rehash_needed: bool
    schema_needed: PasswordSchema | None = None


_hasher_v1 = PasswordHasher(
    time_cost=3,
    memory_cost=8192,  # 8 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


class PasswordHash:
    @staticmethod
    def verify(
        *,
        password_pb: bytes,
        password_schema: PasswordSchema | str,
        password: PasswordType,
        is_test_user: bool,
    ) -> VerifyResult:
        """
        Verify a password against a hash and optional extra data.
        """
        # test user accepts any password in test environment
        if is_test_user:
            return VerifyResult(success=TEST_ENV, rehash_needed=False)
        # preload users contain no password
        if not password_pb:
            return VerifyResult(False, rehash_needed=False)

        password_pb_ = UserPassword.FromString(password_pb)
        password_pb_schema: PasswordSchema = password_pb_.WhichOneof('schema')
        if password_pb_schema != password_schema:
            return VerifyResult(False, rehash_needed=False, schema_needed=password_pb_schema)

        if password_pb_schema == 'v1':
            password_bytes = b64decode(password.get_secret_value(), validate=True)
            if len(password_bytes) != 64:
                raise ValueError(f'Invalid password length, expected 64, got {len(password_bytes)}')
            password_pb_hash = b64encode(password_pb_.v1.hash).strip(b'=').decode()
            password_pb_salt = b64encode(password_pb_.v1.salt).strip(b'=').decode()
            password_pb_digest = f'$argon2id$v=19$m=8192,t=3,p=4${password_pb_salt}${password_pb_hash}'
            try:
                _hasher_v1.verify(password_pb_digest, password_bytes)
                return VerifyResult(True, rehash_needed=False)
            except VerifyMismatchError:
                return VerifyResult(False, rehash_needed=False)

        elif password_pb_schema == 'legacy':
            digest = password_pb_.legacy.digest
            extra = password_pb_.legacy.extra

            # argon2
            if digest.startswith('$argon2'):
                try:
                    _hasher_v1.verify(digest, password.get_secret_value())
                    return VerifyResult(True, rehash_needed=True)
                except VerifyMismatchError:
                    return VerifyResult(False, rehash_needed=True)

            # md5
            if len(digest) == 32:
                salt = extra or ''
                valid_hash = md5((salt + password.get_secret_value()).encode()).hexdigest()  # noqa: S324
                success = compare_digest(digest, valid_hash)
                return VerifyResult(success, rehash_needed=True)

            # pbkdf2
            if '!' in extra:
                password_hashed_b = b64decode(digest)
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
                return VerifyResult(success, rehash_needed=True)

            raise NotImplementedError(f'Unsupported legacy password digest format: {digest[:10]}***, {len(digest)=}')
        raise NotImplementedError(f'Unsupported password_pb schema: {password_pb_schema!r}')

    @staticmethod
    def hash(password_schema: PasswordSchema | str, password: PasswordType) -> bytes | None:
        """
        Hash a password using latest recommended algorithm.

        Returns None if the given password schema cannot be used.
        """
        if password_schema == 'v1':
            password_bytes = b64decode(password.get_secret_value())
            if len(password_bytes) != 64:
                raise ValueError(f'Invalid password length, expected 64, got {len(password_bytes)}')
            hash_string = _hasher_v1.hash(password_bytes)
            prefix, salt, hash = hash_string.rsplit('$', maxsplit=2)
            hash = b64decode(hash + '==')
            salt = b64decode(salt + '==')
            if prefix != '$argon2id$v=19$m=8192,t=3,p=4' or len(hash) != 32 or len(salt) != 16:
                raise AssertionError(f'Invalid hasher configuration: {prefix=!r}, {len(hash)=}, {len(salt)=}')
            return UserPassword(v1=UserPassword.V1(hash=hash, salt=salt)).SerializeToString()

        logging.info('Password schema %r cannot be used for new hashing', password_schema)
        return None
