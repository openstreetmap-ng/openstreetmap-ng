import pytest

from app.lib.legal import get_legal_terms


def test_get_legal_terms():
    for locale in ('FR', 'GB', 'IT'):
        assert '<ol start="8">' in get_legal_terms(locale)
    with pytest.raises(KeyError):
        get_legal_terms('NonExistent')
