import re

from app.lib.yarn_lock import RAPID_VERSION


def test_yarn_lock_version():
    assert re.match(r'^\d+(?:\.\d+)+$', RAPID_VERSION)
