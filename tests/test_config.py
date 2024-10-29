from app.config import VERSION


def test_version_format():
    assert VERSION == 'dev' or VERSION.count('.') == 2, 'VERSION must be in the "dev" or "x.y.z" format'
