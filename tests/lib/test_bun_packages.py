import re

import pytest

from app.lib.bun_packages import RAPID_VERSION


@pytest.mark.parametrize('version', [RAPID_VERSION])
def test_version_pattern(version):
    assert re.match(r'^\d+(?:\.\d+)+$', version)
