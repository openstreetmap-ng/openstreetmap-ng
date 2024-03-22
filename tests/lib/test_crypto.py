from app.lib.crypto import decrypt, encrypt


def test_encryption():
    assert decrypt(encrypt('test')) == 'test'
