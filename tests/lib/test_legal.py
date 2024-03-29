import pytest

from app.lib.legal import legal_terms


def test_legal_terms():
    for locale in ('FR', 'GB', 'IT'):
        assert '<ol start="8">' in legal_terms(locale)
    with pytest.raises(KeyError):
        legal_terms('NonExistent')
