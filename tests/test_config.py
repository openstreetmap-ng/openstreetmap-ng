from app.config import VERSION


def test_version_format():
    assert VERSION == 'dev' or VERSION.startswith('git#'), 'VERSION must be in the "dev" or "git#<commit>" format'
