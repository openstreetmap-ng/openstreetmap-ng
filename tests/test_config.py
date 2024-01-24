import sys

import pytest

from app.config import VERSION


def test_max_str_digits():
    assert sys.int_info.str_digits_check_threshold > 100  # safety check in case the default changes
    int('1' * sys.int_info.str_digits_check_threshold)
    with pytest.raises(ValueError):
        int('1' * (sys.int_info.str_digits_check_threshold + 1))


def test_version_format():
    assert VERSION.count('.') == 2, 'VERSION must be in the "x.y.z" format'
