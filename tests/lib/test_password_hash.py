from pydantic import SecretStr

from app.lib.password_hash import PasswordHash
from app.models.types import PasswordType


def test_password_hash_valid():
    password = PasswordType(SecretStr('password'))
    hashed = PasswordHash.hash(password)
    verified = PasswordHash.verify(hashed, password, is_test_user=False)
    assert verified.success
    assert not verified.rehash_needed


def test_password_hash_argon():
    password = PasswordType(SecretStr('password'))
    hashed = '$argon2id$v=19$m=65536,t=3,p=4$7kKuyNHOoa7+DuH9fNie9A$HeP8nKGegW/SZpf6kxiAPJvFZ0bVIYEzeZwZe3sbjkQ'
    assert PasswordHash.verify(hashed, password, is_test_user=False).success


def test_password_hash_md5():
    password = PasswordType(SecretStr('password'))
    hashed = '67a1e09bb1f83f5007dc119c14d663aa.salt'
    verified = PasswordHash.verify(hashed, password, is_test_user=False)
    assert verified.success
    assert verified.rehash_needed


def test_password_hash_invalid():
    password1 = PasswordType(SecretStr('password1'))
    password2 = PasswordType(SecretStr('password2'))
    hashed = PasswordHash.hash(password1)
    verified = PasswordHash.verify(hashed, password2, is_test_user=False)
    assert not verified.success
    assert not verified.rehash_needed


def test_password_hash_test_user_always_valid():
    password1 = PasswordType(SecretStr('password1'))
    password2 = PasswordType(SecretStr('password2'))
    hashed = PasswordHash.hash(password1)
    verified = PasswordHash.verify(hashed, password2, is_test_user=True)
    assert verified.success
    assert not verified.rehash_needed
