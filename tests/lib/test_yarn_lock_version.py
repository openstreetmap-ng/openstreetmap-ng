import re

from app.lib.yarn_lock_version import yarn_lock_version


def test_yarn_lock_version():
    assert re.match(r'^\d+(?:\.\d+)+$', yarn_lock_version('@rapideditor/rapid'))
