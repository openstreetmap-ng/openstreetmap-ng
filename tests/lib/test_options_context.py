from app.lib.options_context import is_options_context, options_context


def test_options_context():
    with options_context():
        assert is_options_context()


def test_not_options_context():
    assert not is_options_context()
