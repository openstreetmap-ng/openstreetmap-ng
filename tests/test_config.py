from app.config import VERSION


def test_version_format():
    assert VERSION.count('.') == 2, 'VERSION must be in the "x.y.z" format'
