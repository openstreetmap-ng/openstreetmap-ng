from base64 import b64encode

from pydantic import SecretStr

from app.lib.password_hash import PasswordHash, PasswordSchema
from app.models.proto.server_pb2 import UserPassword
from app.models.types import PasswordType


def test_password_hash_v1():
    password_schema: PasswordSchema = 'v1'
    password = PasswordType(SecretStr(b64encode(b'a' * 64).decode()))
    password_pb = PasswordHash.hash(password_schema, password)
    assert password_pb is not None
    verified = PasswordHash.verify(
        password_pb=password_pb,
        password_schema=password_schema,
        password=password,
        is_test_user=False,
    )
    assert verified.success


def test_password_hash_v1_missmatch():
    password_schema: PasswordSchema = 'v1'
    password_1 = PasswordType(SecretStr(b64encode(b'1' * 64).decode()))
    password_2 = PasswordType(SecretStr(b64encode(b'2' * 64).decode()))
    password_pb = PasswordHash.hash(password_schema, password_1)
    assert password_pb is not None
    verified = PasswordHash.verify(
        password_pb=password_pb,
        password_schema=password_schema,
        password=password_2,
        is_test_user=False,
    )
    assert not verified.success


def test_password_hash_v1_test_user():
    password_schema: PasswordSchema = 'v1'
    password_1 = PasswordType(SecretStr(b64encode(b'1' * 64).decode()))
    password_2 = PasswordType(SecretStr(b64encode(b'2' * 64).decode()))
    password_pb = PasswordHash.hash(password_schema, password_1)
    assert password_pb is not None
    verified = PasswordHash.verify(
        password_pb=password_pb,
        password_schema=password_schema,
        password=password_2,
        is_test_user=True,
    )
    assert verified.success


def test_password_hash_legacy_argon():
    password_schema: PasswordSchema = 'legacy'
    password = PasswordType(SecretStr('password'))
    password_pb = UserPassword(
        legacy=UserPassword.Legacy(
            digest='$argon2id$v=19$m=65536,t=3,p=4$7kKuyNHOoa7+DuH9fNie9A$HeP8nKGegW/SZpf6kxiAPJvFZ0bVIYEzeZwZe3sbjkQ',
            extra=None,
        )
    ).SerializeToString()
    assert PasswordHash.verify(
        password_pb=password_pb,
        password_schema=password_schema,
        password=password,
        is_test_user=False,
    ).success


def test_password_hash_legacy_md5():
    password_schema: PasswordSchema = 'legacy'
    password = PasswordType(SecretStr('password'))
    password_pb = UserPassword(
        legacy=UserPassword.Legacy(
            digest='67a1e09bb1f83f5007dc119c14d663aa',
            extra='salt',
        )
    ).SerializeToString()
    assert PasswordHash.verify(
        password_pb=password_pb,
        password_schema=password_schema,
        password=password,
        is_test_user=False,
    ).success
