from base64 import b64encode

from pydantic import SecretStr

from app.config import TEST_USER_EMAIL_SUFFIX
from app.lib.password_hash import PasswordHash
from app.models.db.user import User
from app.models.proto.server_pb2 import UserPassword
from app.models.proto.shared_pb2 import TransmitUserPassword
from app.models.types import Email, Password


def _user(password_pb: bytes, *, is_test_user: bool = False) -> User:
    return {
        'email': Email(
            f'user{TEST_USER_EMAIL_SUFFIX if is_test_user else "@example.com"}'
        ),
        'password_pb': password_pb,
    }  # type: ignore


def test_password_hash_v1():
    password = TransmitUserPassword(v1=b'a' * 64)
    password = Password(SecretStr(b64encode(password.SerializeToString()).decode()))
    password_pb = PasswordHash.hash(password)
    assert password_pb is not None

    verified = PasswordHash.verify(_user(password_pb), password)
    assert verified.success


def test_password_hash_v1_mismatch():
    password_1 = TransmitUserPassword(v1=b'a' * 64)
    password_1 = Password(SecretStr(b64encode(password_1.SerializeToString()).decode()))
    password_2 = TransmitUserPassword(v1=b'b' * 64)
    password_2 = Password(SecretStr(b64encode(password_2.SerializeToString()).decode()))
    password_pb = PasswordHash.hash(password_1)
    assert password_pb is not None

    verified = PasswordHash.verify(_user(password_pb), password_2)
    assert not verified.success


def test_password_hash_v1_test_user():
    password_1 = TransmitUserPassword(v1=b'a' * 64)
    password_1 = Password(SecretStr(b64encode(password_1.SerializeToString()).decode()))
    password_2 = TransmitUserPassword(v1=b'b' * 64)
    password_2 = Password(SecretStr(b64encode(password_2.SerializeToString()).decode()))
    password_pb = PasswordHash.hash(password_1)
    assert password_pb is not None

    verified = PasswordHash.verify(_user(password_pb, is_test_user=True), password_2)
    assert verified.success


def test_password_hash_legacy_unsupported():
    password = TransmitUserPassword(legacy='password')
    password = Password(SecretStr(b64encode(password.SerializeToString()).decode()))
    password_pb = PasswordHash.hash(password)
    assert password_pb is None


def test_password_hash_legacy_argon():
    password = TransmitUserPassword(legacy='password')
    password = Password(SecretStr(b64encode(password.SerializeToString()).decode()))
    password_pb = UserPassword(
        legacy=UserPassword.Legacy(
            digest='$argon2id$v=19$m=65536,t=3,p=4$7kKuyNHOoa7+DuH9fNie9A$HeP8nKGegW/SZpf6kxiAPJvFZ0bVIYEzeZwZe3sbjkQ',
            extra=None,
        )
    ).SerializeToString()

    assert PasswordHash.verify(_user(password_pb), password).success


def test_password_hash_legacy_md5():
    password = TransmitUserPassword(legacy='password')
    password = Password(SecretStr(b64encode(password.SerializeToString()).decode()))
    password_pb = UserPassword(
        legacy=UserPassword.Legacy(
            digest='67a1e09bb1f83f5007dc119c14d663aa',
            extra='salt',
        )
    ).SerializeToString()

    assert PasswordHash.verify(_user(password_pb), password).success
