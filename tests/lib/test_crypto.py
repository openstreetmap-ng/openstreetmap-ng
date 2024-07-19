import pytest

from app.lib.crypto import decrypt, encrypt, hash_bytes, hash_hex


def test_hash():
    assert hash_bytes('test').hex() == hash_hex('test')


def test_hash_repeatable():
    assert hash_bytes('test') == hash_bytes('test')


def test_encrypt_roundtrip():
    assert decrypt(encrypt('test')) == 'test'


def test_encrypt_unique():
    assert encrypt('test1') != encrypt('test1')


def test_encrypt_prevent_empty_string():
    with pytest.raises(AssertionError):
        encrypt('')
