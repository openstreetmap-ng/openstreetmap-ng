from math import isclose

import pytest

from app.lib.shortlink import shortlink_decode, shortlink_encode


@pytest.mark.parametrize(
    'input',
    [
        (0, 0, 5),
        (156, 45, 17),
        (1.23456789, 2.34567891, 20),
    ],
)
def test_encode_decode(input):
    encoded = shortlink_encode(*input)
    decoded = shortlink_decode(encoded)

    for a, b in zip(input, decoded, strict=True):
        assert isclose(a, b, abs_tol=0.01)


@pytest.mark.parametrize(
    ('input', 'output'),
    [
        ('0OP4tXGMB', (19.57922, 51.87695, 19)),
        ('ecetE--', (-31.113, 64.130, 6)),
    ],
)
def test_decode(input, output):
    decoded = shortlink_decode(input)

    for a, b in zip(output, decoded, strict=True):
        assert isclose(a, b, abs_tol=0.01)
