from app.lib.password_hash import PasswordHash
from app.models.proto.server_pb2 import UserPassword
from app.models.proto.shared_pb2 import TransmitUserPassword
from app.models.types import Password


def test_password_hash_v1():
    password = TransmitUserPassword(v1=b'a' * 64)
    password = Password(password.SerializeToString())
    password_pb = PasswordHash.hash(password)
    assert password_pb is not None

    verified = PasswordHash.verify(password_pb, password)
    assert verified.success


def test_password_hash_v1_mismatch():
    password_1 = TransmitUserPassword(v1=b'a' * 64)
    password_1 = Password(password_1.SerializeToString())
    password_2 = TransmitUserPassword(v1=b'b' * 64)
    password_2 = Password(password_2.SerializeToString())
    password_pb = PasswordHash.hash(password_1)
    assert password_pb is not None

    verified = PasswordHash.verify(password_pb, password_2)
    assert not verified.success


def test_password_hash_legacy_unsupported():
    password = TransmitUserPassword(legacy='password')
    password = Password(password.SerializeToString())
    password_pb = PasswordHash.hash(password)
    assert password_pb is None


def test_password_hash_legacy_argon():
    password = TransmitUserPassword(legacy='password')
    password = Password(password.SerializeToString())
    password_pb = UserPassword(
        legacy=UserPassword.Legacy(
            digest='$argon2id$v=19$m=65536,t=3,p=4$7kKuyNHOoa7+DuH9fNie9A$HeP8nKGegW/SZpf6kxiAPJvFZ0bVIYEzeZwZe3sbjkQ',
            extra=None,
        )
    ).SerializeToString()

    assert PasswordHash.verify(password_pb, password).success


def test_password_hash_legacy_md5():
    password = TransmitUserPassword(legacy='password')
    password = Password(password.SerializeToString())
    password_pb = UserPassword(
        legacy=UserPassword.Legacy(
            digest='67a1e09bb1f83f5007dc119c14d663aa',
            extra='salt',
        )
    ).SerializeToString()

    assert PasswordHash.verify(password_pb, password).success
