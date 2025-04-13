import pytest

from app.lib.referrer import secure_referrer


@pytest.mark.parametrize(
    ('referer', 'expected'),
    [
        (None, '/'),
        ('https://example.com', '/'),
        ('https://example.com/test', '/'),
        ('/test', '/test'),
        ('/test?key=value', '/test?key=value'),
    ],
)
def test_secure_referrer(referer, expected):
    assert secure_referrer(referer) == expected
