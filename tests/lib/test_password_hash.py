from app.lib.password_hash import PasswordHash
from app.models.str import PasswordStr


def test_password_hash_current():
    password = PasswordStr('password')
    hashed = PasswordHash.hash(password)
    verified = PasswordHash.verify(hashed, None, password)
    assert verified.success
    assert not verified.rehash_needed


def test_password_hash_argon():
    password = PasswordStr('password')
    hashed = '$argon2id$v=19$m=65536,t=3,p=4$7kKuyNHOoa7+DuH9fNie9A$HeP8nKGegW/SZpf6kxiAPJvFZ0bVIYEzeZwZe3sbjkQ'
    assert PasswordHash.verify(hashed, None, password).success


def test_password_hash_md5():
    salt = 'salt'
    password = PasswordStr('password')
    hashed = '67a1e09bb1f83f5007dc119c14d663aa'
    verified = PasswordHash.verify(hashed, salt, password)
    assert verified.success
    assert not verified.rehash_needed


def test_password_hash_invalid():
    password1 = PasswordStr('password1')
    password2 = PasswordStr('password2')
    hashed = PasswordHash.hash(password1)
    verified = PasswordHash.verify(hashed, None, password2)
    assert not verified.success
    assert not verified.rehash_needed
