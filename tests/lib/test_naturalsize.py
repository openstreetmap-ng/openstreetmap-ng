import pytest

from app.lib.naturalsize import naturalsize


@pytest.mark.parametrize(
    ('size', 'expected'),
    [
        (10000, '9.77 KiB'),
        (1024, '1.00 KiB'),
        (1023, '1023 B'),
    ],
)
def test_naturalsize(size, expected):
    assert naturalsize(size) == expected
