import pytest

from app.lib.sizestr import sizestr


@pytest.mark.parametrize(
    ('size', 'expected'),
    [
        (10000, '9.77 KiB'),
        (15000000, '14.3 MiB'),
        (-42, '-42 B'),
        (float('inf'), '(inf)'),
    ],
)
def test_sizestr(size, expected):
    assert sizestr(size) == expected
