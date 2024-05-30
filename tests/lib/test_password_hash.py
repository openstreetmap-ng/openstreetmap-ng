from app.lib.password_hash import PasswordHash
from app.models.str import PasswordStr


def test_password_hash_current():
    ph = PasswordHash()
    password = PasswordStr('password')
    hashed = ph.hash(password)
    assert ph.verify(hashed, None, password)
    assert not ph.rehash_needed


def test_password_hash_argon():
    ph = PasswordHash()
    password = PasswordStr('password')
    hashed = '$argon2id$v=19$m=65536,t=3,p=4$7kKuyNHOoa7+DuH9fNie9A$HeP8nKGegW/SZpf6kxiAPJvFZ0bVIYEzeZwZe3sbjkQ'
    assert ph.verify(hashed, None, password)


def test_password_hash_md5():
    ph = PasswordHash()
    salt = 'salt'
    password = PasswordStr('password')
    hashed = '67a1e09bb1f83f5007dc119c14d663aa'
    assert ph.verify(hashed, salt, password)
    assert ph.rehash_needed


def test_password_hash_invalid():
    ph = PasswordHash()
    password1 = PasswordStr('password1')
    password2 = PasswordStr('password2')
    hashed = ph.hash(password1)
    assert not ph.verify(hashed, None, password2)
    assert not ph.rehash_needed
