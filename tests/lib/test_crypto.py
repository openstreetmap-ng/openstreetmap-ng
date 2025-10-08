from app.lib.crypto import hash_bytes, hmac_bytes


def test_hash_repeatable():
    assert hash_bytes('test') == hash_bytes('test')


def test_hash_hmac():
    assert hmac_bytes(b'test') != hash_bytes(b'test')


# def test_encrypt_roundtrip():
#     assert decrypt(encrypt('test')) == 'test'


# def test_encrypt_unique():
#     assert encrypt('test1') != encrypt('test1')


# def test_encrypt_prevent_empty_string():
#     with pytest.raises(AssertionError):
#         encrypt('')


# def test_decrypt_empty():
#     assert not decrypt(b'')
