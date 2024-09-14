import re

import pytest

from app.config import RAPID_VERSION, VERSION


def test_version_format():
    assert VERSION == 'dev' or VERSION.count('.') == 2, 'VERSION must be in the "dev" or "x.y.z" format'


@pytest.mark.parametrize('version', [RAPID_VERSION])
def test_yarnlock_version(version):
    assert re.match(r'^\d+(?:\.\d+)+$', version)
