from app.lib.openid import parse_openid_token_no_verify


def test_parse_openid_token():
    token = parse_openid_token_no_verify(
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
    )
    assert token['sub'] == '1234567890'
    assert token.get('name') == 'John Doe'
    assert token['iat'] == 1516239022
