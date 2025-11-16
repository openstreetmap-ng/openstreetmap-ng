from base64 import b64decode, b64encode
from hashlib import md5, pbkdf2_hmac
from hmac import compare_digest
from typing import Literal, NamedTuple

import cython
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError

from app.config import ENV, SECRET_32
from app.models.db.user import User, user_is_test
from app.models.proto.server_pb2 import UserPassword
from app.models.proto.shared_pb2 import TransmitUserPassword
from app.models.types import Password

PasswordSchema = Literal['legacy', 'v1']


class VerifyResult(NamedTuple):
    success: bool
    rehash_needed: bool
    schema_needed: PasswordSchema | None = None


_HASHER_V1 = PasswordHasher(
    time_cost=3,
    memory_cost=8192,  # 8 MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


class PasswordHash:
    @staticmethod
    def hash(password: Password) -> bytes | None:
        """
        Hash a password using the latest recommended algorithm.
        Returns None if the given password schema cannot be used.
        """
        transmit_password = TransmitUserPassword.FromString(
            b64decode(password.get_secret_value())
        )
        if transmit_password.v1:
            return _hash_v1(transmit_password.v1)

        return None

    @staticmethod
    def verify(user: User, password: Password):
        """Verify a password against a hash and optional extra data."""
        # test user accepts any password in test environment
        if user_is_test(user):
            return VerifyResult(success=ENV != 'prod', rehash_needed=False)
        # preload users contain no password
        if not user['password_pb']:
            return VerifyResult(False, rehash_needed=False)

        transmit_password = TransmitUserPassword.FromString(
            b64decode(password.get_secret_value())
        )
        password_pb_ = UserPassword.FromString(user['password_pb'])
        password_pb_schema: PasswordSchema = password_pb_.WhichOneof('schema')

        if password_pb_schema == 'v1':
            return _verify_v1(transmit_password.v1, password_pb_.v1)
        if password_pb_schema == 'legacy':
            return _verify_legacy(transmit_password.legacy, password_pb_.legacy)

        raise NotImplementedError(
            f'Unsupported password_pb schema: {password_pb_schema!r}'
        )


@cython.cfunc
def _hash_v1(password_bytes: bytes) -> bytes:
    if len(password_bytes) != 64:
        raise ValueError(
            f'Invalid password length, expected 64, got {len(password_bytes)}'
        )

    hash_string = _HASHER_V1.hash(password_bytes + SECRET_32.get_secret_value())
    prefix, salt, hash = hash_string.rsplit('$', 2)
    hash = b64decode(hash + '==')
    salt = b64decode(salt + '==')
    assert (
        prefix == '$argon2id$v=19$m=8192,t=3,p=4'
        and len(hash) == 32
        and len(salt) == 16
    ), f'Invalid hasher configuration: {prefix=!r}, {len(hash)=}, {len(salt)=}'

    return UserPassword(v1=UserPassword.V1(hash=hash, salt=salt)).SerializeToString()


@cython.cfunc
def _verify_v1(password_bytes: bytes, password_pb_v1: UserPassword.V1):
    if not password_bytes:
        return VerifyResult(False, rehash_needed=False, schema_needed='v1')
    if len(password_bytes) != 64:
        raise ValueError(
            f'Invalid password length, expected 64, got {len(password_bytes)}'
        )

    password_pb_hash = b64encode(password_pb_v1.hash).rstrip(b'=').decode()
    password_pb_salt = b64encode(password_pb_v1.salt).rstrip(b'=').decode()
    password_pb_digest = (
        f'$argon2id$v=19$m=8192,t=3,p=4${password_pb_salt}${password_pb_hash}'
    )

    try:
        _HASHER_V1.verify(
            password_pb_digest, password_bytes + SECRET_32.get_secret_value()
        )
        return VerifyResult(True, rehash_needed=False)
    except VerifyMismatchError:
        return VerifyResult(False, rehash_needed=False)


@cython.cfunc
def _verify_legacy(password_text: str, password_pb_legacy: UserPassword.Legacy):
    if not password_text:
        return VerifyResult(False, rehash_needed=False, schema_needed='legacy')

    digest = password_pb_legacy.digest
    extra = password_pb_legacy.extra

    if digest.startswith('$argon2'):
        return _verify_legacy_argon2(password_text, digest)
    if len(digest) == 32:
        return _verify_legacy_md5(password_text, digest, extra)
    if '!' in extra:
        return _verify_legacy_pbkdf2(password_text, digest, extra)

    raise NotImplementedError(
        f'Unsupported legacy password digest format: {digest[:10]}***, {len(digest)=}'
    )


@cython.cfunc
def _verify_legacy_argon2(password_text: str, digest: str):
    try:
        _HASHER_V1.verify(digest, password_text)
        return VerifyResult(True, rehash_needed=True)
    except VerifyMismatchError:
        return VerifyResult(False, rehash_needed=True)


@cython.cfunc
def _verify_legacy_md5(password_text: str, digest: str, extra: str):
    salt = extra or ''
    valid_hash = md5((salt + password_text).encode()).hexdigest()  # noqa: S324
    success = compare_digest(digest, valid_hash)
    return VerifyResult(success, rehash_needed=True)


@cython.cfunc
def _verify_legacy_pbkdf2(password_text: str, digest: str, extra: str):
    password_hashed_b = b64decode(digest)
    algorithm, iterations, salt = extra.split('!', 2)
    valid_hash_b = pbkdf2_hmac(
        hash_name=algorithm,
        password=password_text.encode(),
        salt=salt.encode(),
        iterations=int(iterations),
        dklen=len(password_hashed_b),
    )
    success = compare_digest(password_hashed_b, valid_hash_b)
    return VerifyResult(success, rehash_needed=True)
