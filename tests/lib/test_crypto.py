import pytest

from app.lib.crypto import decrypt, encrypt, hash_bytes, hash_hex, hmac_bytes


def test_hash_hex():
    assert hash_bytes('test').hex() == hash_hex('test')


def test_hash_repeatable():
    assert hash_bytes('test') == hash_bytes('test')


def test_hash_hmac():
    assert hmac_bytes(b'test') != hash_bytes(b'test')


def test_encrypt_roundtrip():
    assert decrypt(encrypt('test')) == 'test'


def test_encrypt_unique():
    assert encrypt('test1') != encrypt('test1')


def test_encrypt_prevent_empty_string():
    with pytest.raises(AssertionError):
        encrypt('')


def test_decrypt_empty():
    assert decrypt(b'') == ''
